from fastapi.testclient import TestClient
import httpx
from main import app, http_client,parse_page,send_req_to_groq,Scrape_res  
import pytest
import asyncio

client = TestClient(app)

def test_scrape_webpage():
	response = client.get("/scrape/webpage", params={"url":"https://example.com"})
	assert response.status_code == 200
	assert isinstance(response.json(), str)

@pytest.mark.asyncio
async def test_http_client():
	response = await http_client("https://example.com")
	assert isinstance(response, httpx.Response)

@pytest.mark.asyncio
async def test_parse_parge():
	res = await http_client("https://example.com")
	payload = parse_page(res,"https://example.com")
	assert isinstance(payload, Scrape_res)
