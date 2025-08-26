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

def validate_url_manually(url:str) -> bool:
    	try:
        	result = urlparse(url)
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

class File_handler:
	def __init__(self):
		pass

	def return_prompt_template(self, filepath):
		try:
			with open(filepath, 'r') as f:
        			prompt = Template(f.read())
		except Exception as e:
    			raise RuntimeError(f"error while reading prompt file")
		return prompt

class Api_caller:
	def __init__(self):	
		self.api_key = os.getenv("GROQ_API_KEY").strip()
		if not self.api_key:
			raise RuntimeError("api key not found")

		try:
			self.client = AsyncGroq(
			api_key=self.api_key,
        		)
		except Exception as e:
    			raise RuntimeError(f"error while building groq client")

	async def send_req_to_groq(self, result: dict, prompt:str) -> str:
    		prompt_final = prompt.render(title=result["title"], desc=result["description"], page_content=result["content"], url=result["url"])
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

class Format_handler:
	def __init__(self):
		pass
 
	def turn_api_res_to_html(self, api_res) -> str:
		return markdown.markdown(api_res)

@app.get('/scraper/webpage')
async def summarize_webpage(url:str = Query()):

	scraper = Web_scraper()
	handler = File_handler()
	caller = Api_caller()
	formatter = Format_handler()

	is_valid = validate_url_manually(url)
	if not is_valid:
		raise HTTPException(status_code=400, detail='invalid url')

	raw_html = await scraper.scrape_webpage(url)
	result_dict = scraper.parse_page(raw_html, url)
	prompt = handler.return_prompt_template('prompts/prompt.txt')
	api_res = await caller.send_req_to_groq(result_dict, prompt)
	content = formatter.turn_api_res_to_html(api_res)
	return HTMLResponse(content=content)
