from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
import httpx
from bs4 import BeautifulSoup
import asyncio
from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Union
from groq import AsyncGroq
import os
from dotenv import load_dotenv
from jinja2 import Template
from urllib.parse import urlparse
import markdown

load_dotenv()
app = FastAPI()

#prompt str
try:
	with open('prompts/prompt.txt', 'r') as f:
        	PROMPT = Template(f.read())
except Exception as e:
    	raise RuntimeError(f"error while reading prompt file")

# api key
API_KEY = os.getenv("GROQ_API_KEY").strip()
if not API_KEY:
	raise KeyError("api key not found")

# groq client
try:
	CLIENT = AsyncGroq(
		api_key=API_KEY,
        	)
except Exception as e:
    	raise RuntimeError(f"error while building groq client: {str(e)}")

def validate_url_manually(url:str) -> bool:
	try:
		result = urlparse(url)
		if result.scheme != 'https':
			raise HTTPException(status_code=400, detail='nemon only supports scraping of url with https scheme')
		if result.netloc in ['localhost', '127.0.0.1', '0.0.0.0', '198.168.1.1', '10.0.0.1', '172.16.0.1']:
			raise HTTPException(status_code=400, detail='invalid url')
		return all([result.scheme, result.netloc])
	except Exception:
		return False

class Web_scraper:
	def __init__ (self):
		pass
	
	async def scrape_webpage(self, url:str) -> httpx.Response:
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
	
	def parse_page(self, res: httpx.Response, url:str) -> dict:
    		soup = BeautifulSoup(res.text, 'html.parser')
    		title = soup.find('title')
    		desc = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attr={'property':'og:description'})
    		paragraphs = soup.find_all('p')
    		para_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

    		if len(para_text)>1000:
        		para_text = para_text[:1000]

    		for tags in soup(["script", "style", "nav", "footer", "aside", "advertisement"]):
        		tags.decompose()

    		result = {
            		"url":url,
            		"title":title.text.strip() if title else "No title found for this url",
            		"description":desc.get("content","").strip() if desc else "No description found for this url",
            		"content":para_text if para_text else "No content found on this url"
           		}
    		return result


class Api_caller:
	def __init__(self, prompt:str, client: AsyncGroq):
		self.prompt = prompt
		self.client = client
	async def send_req_to_groq(self, result: dict) -> str:
    		prompt_final = self.prompt.render(title=result["title"], desc=result["description"], page_content=result["content"], url=result["url"])
    		try:
        		chat_completion = await self.client.chat.completions.create(
            			messages=[
                			{
                    			"role": "user",
                    			"content": prompt_final,
                			}
            			],
            			model="llama-3.1-8b-instant",
        			)
        		message = chat_completion.choices[0].message.content
    		except Exception as e:
        		raise HTTPException(status_code=500, detail=f"err: error while making api call to groq")
    		return message


@app.get('/scraper/webpage')
async def summarize_webpage(url:str = Query()):

	scraper = Web_scraper()
	caller = Api_caller(PROMPT, CLIENT)

	is_valid = validate_url_manually(url)
	if not is_valid:
		raise HTTPException(status_code=400, detail='invalid url')

	raw_html = await scraper.scrape_webpage(url)
	result_dict = scraper.parse_page(raw_html, url)
	api_res = await caller.send_req_to_groq(result_dict)
	return HTMLResponse(content=markdown.markdown(api_res))
