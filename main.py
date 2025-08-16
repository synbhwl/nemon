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

@app.post('/find')
async def scarpe(req: Scrape_req):
    headers = {'User-Agent':'Mozilla/5.0'}
    try:
        async with httpx.AsyncClient() as client:
            res = await client.get(str(req.url), headers=headers)
            res.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"err while sending request to target url: {str(e)}")

    soup = BeautifulSoup(res.text, 'html.parser')
    title = soup.find('title')
    desc = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attr={'property':'og:description'})

    result = Scrape_res(
            url=req.url,
            title=title.text.strip() if title else "there is no title for the url",
            description=desc.content.strip() if desc else "there is no decription for this url"
            )

    return result
