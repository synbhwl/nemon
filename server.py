from fastapi import FastAPI, HTTPException
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
import asyncio
import markdown

load_dotenv()
app = FastAPI()



# api key from env
api_key = os.getenv("GROQ_API_KEY").strip()
if not api_key:
	raise RuntimeError("api key not found")

# initialising groq client
try:
	client = AsyncGroq(
	api_key=api_key,
        )
except Exception as e:
    	raise RuntimeError(f"error while making groq client {str(e)}")
	
# globally opening file to avoid keep opening it over and over again for every route
try:
	with open('prompts/prompt.txt', 'r') as f:
        	prompt = Template(f.read())
except Exception as e:
    	raise RuntimeError(f"error while reading prompt file: {str(e)}")



# this class will hold everything for now
class Webpage_scraper:
	def __init__(self, url:str=None, title:str=None, content:str=None, description:str=None, res:httpx.Response=None, api_res:str=None):
		self.url = url
		self.title = title
		self.content = content
		self.description = description
		self.res = res
		self.api_res = api_res
	
	# instead of using an HttpUrl type for validation that conflicts sometimes with SQLalchemy, i am using a manual validation 
	def validate_url_manually(self) -> bool:
    		try:
        		result = urlparse(self.url)
        		return all([result.scheme, result.netloc])
    		except Exception:
        		return False

	
	async def scrape_webpage(self) -> httpx.Response:
    		headers = {'User-Agent':'Mozilla/5.0'}
    		timeout = httpx.Timeout(15.0)
    		try:
       			async with httpx.AsyncClient(timeout=timeout) as client:
            			res = await client.get(str(self.url), headers=headers,follow_redirects=True)
            			res.raise_for_status()

            			if len(res.content)> 10_00_000:
                			raise HTTPException(status_code=413, detail="page too large (max 10mb)")
            
    		except Exception as e:
        		raise HTTPException(status_code=400, detail=f"err while sending request to target url: {str(e)}: network issue or url doesn't exist.")
    
    		return res
	
	def parse_page(self) -> dict:
    		soup = BeautifulSoup(self.res.text, 'html.parser')
    		title = soup.find('title')
    		desc = soup.find('meta', attrs={'name':'description'}) or soup.find('meta', attr={'property':'og:description'})
    		paragraphs = soup.find_all('p')
    		para_text = ' '.join(p.get_text(strip=True) for p in paragraphs)

    		if len(para_text)>1000:
        		para_text = para_text[:1000]

    		for tags in soup(["script", "style", "nav", "footer", "aside", "advertisement"]):
        		tags.decompose()

    		result = {
            		"url":self.url,
            		"title":title.text.strip() if title else "No title found for this url",
            		"description":desc.get("content","").strip() if desc else "No description found for this url",
            		"content":para_text if para_text else "No content found on this url"
           		}
    		return result
	
	async def send_req_to_groq(self) -> str:
    		prompt_final = prompt.render(title=self.title, desc=self.description, page_content=self.content, url=self.url)
    		try:
        		chat_completion = await client.chat.completions.create(
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
        		raise HTTPException(status_code=500, detail=f"err: error while making api call to groq: {str(e)}")
    		return message

	def turn_api_res_to_html(self) -> str:
		return markdown.markdown(self.api_res.decode('utf-8'))


# route that will listen for requests from users
@app.get('/scrape/webpage')
async def summarize_webpage(url: str):
	scraper = Webpage_scraper(url=url)
	isvalid = scraper.validate_url_manually()
	if not isvalid:
        	raise HTTPException(status_code=400, detail="invalid url")

	raw_webpage = await scraper.scrape_webpage()
	scraper.res = raw_webpage
	payload_dict = scraper.parse_page()
	scraper.title = payload_dict["title"]
	scraper.description = payload_dict["description"]
	scraper.content = payload_dict["content"]
	
	api_res =await scraper.send_req_to_groq()
	scraper.api_res = api_res.encode('utf-8')

	html_res = scraper.turn_api_res_to_html()
	return HTMLResponse(content=html_res)
