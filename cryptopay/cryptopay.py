import aiohttp
import logging
import requests
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class CryptoPayAPI:
    def __init__(self, api_token):
        self.api_token = api_token
        self.base_url = "https://pay.crypt.bot/api/"

    def _request(self, method, params=None):
        headers = {"Crypto-Pay-API-Token": self.api_token}
        url = self.base_url + method

        logging.info(f"Sending request to {url} with params: {params}")

        if method in ["getMe", "getInvoices"]:
            response = requests.get(url, headers=headers, params=params)
        else:
            response = requests.post(url, headers=headers, json=params)

        try:
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP error occurred: {e} - Response: {response.text}")
            raise
        except Exception as e:
            logging.error(f"Error occurred: {e}")
            raise

    async def get_me(self):
        return await self._request("getMe", {})

    def create_invoice(self, amount, description=None, hidden_message=None,
                      paid_btn_name=None, paid_btn_url=None, payload=None,
                      allow_comments=True, allow_anonymous=True, expires_in=None):
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Amount must be a positive number")

        params = {
            "currency_type": "fiat",
            "fiat": "USD",
            "amount": amount,
            "description": description,
            "hidden_message": hidden_message,
            "paid_btn_name": paid_btn_name,
            "paid_btn_url": paid_btn_url,
            "payload": payload,
            "allow_comments": allow_comments,
            "allow_anonymous": allow_anonymous,
            "expires_in": expires_in
        }

        params = {k: v for k, v in params.items() if v is not None}
        return self._request("createInvoice", params)

    def transfer(self, user_id, asset, amount, spend_id, disable_send_notification=False):
        params = {
            "user_id": user_id,
            "asset": asset,
            "amount": amount,
            "spend_id": spend_id,
            "disable_send_notification": disable_send_notification
        }
        return self._request("transfer", params)

    async def get_invoice_status(self, invoice_id: str):
        params = {"invoice_ids": invoice_id}
        result = await self._async_request("GET", "getInvoices", params)
        if result.get("result") and len(result["result"]["items"]) > 0:
            return result["result"]["items"][0].get("status")
        return None

    async def _async_request(self, method: str, endpoint: str, params: dict = None):
        headers = {
            "Crypto-Pay-API-Token": self.api_token,
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            url = f"{self.base_url}{endpoint}"
            try:
                async with session.request(method, url, json=params) as response:
                    if response.status != 200:
                        raise Exception(f"API request failed with status {response.status}")
                    return await response.json()
            except Exception as e:
                raise Exception(f"API request failed: {e}")

    async def is_invoice_paid(self, invoice_id: str) -> bool:
        url = f"{self.base_url}invoices/{invoice_id}"
        headers = {"Crypto-Pay-API-Token": self.api_token}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    return False

                data = await response.json()
                status = data["result"]["status"]
                return status == "paid"

    async def get_balance(self):
        return await self._async_request("POST", "getBalance", {})

    async def get_exchange_rates(self):
        return await self._async_request("POST", "getExchangeRates", {})

    async def get_currencies(self):
        return await self._async_request("POST", "getCurrencies", {})

def get_payment_invoice_keyboard(pay_url: str) -> InlineKeyboardMarkup:
    text = "💰 Перейти к оплате"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, url=pay_url)]
    ])

async def check_invoice_paid(invoice_id: str, api_key: str) -> bool:
    url = f"https://pay.crypt.bot/api/invoices/{invoice_id}"
    headers = {"Crypto-Pay-API-Token": api_key}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                return False

            data = await response.json()
            status = data["result"]["status"]
            return status == "paid"
