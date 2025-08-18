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

load_dotenv()

app = FastAPI()

api_key = os.getenv("GROQ_API_KEY").strip()
if not api_key:
    raise HTTPException(status_code=500, detail="api key not found")

client = Groq(
    api_key=api_key,
    )

class Scrape_req(BaseModel):
    url:HttpUrl

class Scrape_res(BaseModel):
    url: HttpUrl
    title: Optional[str]
    description: Optional[str]
    content: Optional[str]

async def http_client(req: Scrape_req):
    headers = {'User-Agent':'Mozilla/5.0'}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(str(req.url), headers=headers)
            res.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"err while sending request to target url: {str(e)}")
    
    return res

def parse_page(res: httpx.Response, req: Scrape_req):
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
            url=req.url,
            title=title.text.strip() if title else "No title found for this url",
            description=desc.get("content","").strip() if desc else "No description found for this url",
            content=para_text if para_text else "No content found on this url"
            )

    return result

def read_prompt(payload: Scrape_res):
    try:
        with open('prompts/prompt.txt') as f:
            prompt = Template(f.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"err: error while reading prompt file {str(e)}")

    prompt_final = prompt.render(title=payload.title, desc=payload.description, page_content=payload.content, url=payload.url)
    return prompt_final

def send_req_to_groq(payload: Scrape_res):
    prompt_final = read_prompt(payload)
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

@app.post('/scrape/webpage')
async def scarpe_webpage(req: Scrape_req):
    res = await http_client(req)
    payload = parse_page(res, req)
    api_res = send_req_to_groq(payload) 
    return api_res
## should be fine
