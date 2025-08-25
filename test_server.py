from fastapi.testclient import TestClient
import httpx
from main import app, http_client,parse_page,send_req_to_groq,Scrape_res  
import pytest
import asyncio
from asyncmock import AsyncMock
from unittest.mock import patch
client = TestClient(app)

dummy_payload= Scrape_res(
            url="https://whatever.com",
            title="whatever is the name",
            description="whatever is the description",
            content="whatever is the content"
            )

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

@pytest.mark.asyncio
async def test_making_api_call_to_groq(mocker):
	mock_chat_completion =AsyncMock()
	mock_chat_completion.choices = [AsyncMock()]
	mock_chat_completion.choices[0].message.content = "whatever is the response"

	with patch("main.client.chat.completions.create",return_value=mock_chat_completion):
		response = await send_req_to_groq(dummy_payload)
	assert response == "whatever is the response"
