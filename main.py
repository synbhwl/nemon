from fastapi import FastAPI, HTTPException
import httpx
from bs4 import BeautifulSoup
import asyncio
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional 
from groq import Groq
import os
from dotenv import load_dotenv
from jinja2 import Template
from urllib.parse import urlparse

load_dotenv()

app = FastAPI()

api_key = os.getenv("GROQ_API_KEY").strip()
if not api_key:
    raise RuntimeError("api key not found")


#this needs to be fixed
try:
    client = Groq(
        api_key=api_key,
        )
except Exception as e:
    raise RuntimeError(f"error while making groq client {str(e)}")

try:
    with open('prompts/prompt.txt', 'r') as f:
        prompt = Template(f.read())
except Exception as e:
    raise RuntimeError(f"error while reading prompt file: {str(e)}")


class Scrape_res(BaseModel):
    url: HttpUrl
    title: Optional[str]
    description: Optional[str]
    content: Optional[str]

def url_manual_validation(url: str):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

async def http_client(url: str):
    headers = {'User-Agent':'Mozilla/5.0'}
    timeout = httpx.Timeout(15.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.get(str(url), headers=headers,follow_redirects=True)
            res.raise_for_status()

            if len(res.content)> 10_00_000:
                raise HTTPException(status_code=413, detail="page too large (max 10mb)")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"err while sending request to target url: {str(e)}: network issue or url doesn't exist.")
    
    return res

def parse_page(res: httpx.Response, url: str):
    soup = BeautifulSoup(res.text, 'html.parser')
    title = soup.find('title')
    desc = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attr={'property':'og:description'})
    paragraphs = soup.find_all('p')
    para_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

    if len(para_text)>1000:
        para_text = para_text[:1000]

    for tags in soup(["script", "style", "nav", "footer", "aside", "advertisement"]):
        tags.decompose()
    
    result = Scrape_res(
            url=url,
            title=title.text.strip() if title else "No title found for this url",
            description=desc.get("content","").strip() if desc else "No description found for this url",
            content=para_text if para_text else "No content found on this url"
            )

    return result

def send_req_to_groq(payload: Scrape_res):
    prompt_final = prompt.render(title=payload.title, desc=payload.description, page_content=payload.content, url=payload.url)
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt_final,
                }
            ],
            model="llama3-70b-8192",
        )
        message = chat_completion.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"err: error while making api call to groq: {str(e)}")
    return message

@app.get('/scrape/webpage')
async def scarpe_webpage(url: str):
    isvalid = url_manual_validation(url)
    if not isvalid:
        raise HTTPException(status_code=400, detail="invalid url")
    res = await http_client(url)
    payload = parse_page(res,url)
    api_res = send_req_to_groq(payload) 
    return api_res
