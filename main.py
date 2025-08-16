from fastapi import FastAPI, HTTPException
import httpx
from bs4 import BeautifulSoup
import asyncio
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional 


app = FastAPI()

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
            description=desc.content.strip() if desc else "No description found for this url",
            content=para_text if para_text else "No content found on this url"
            )

    return result


@app.post('/find')
async def scarpe(req: Scrape_req):
    res = await http_client(req)
    result= parse_page(res, req)
    return result

## should be fine
