from flask import Flask, render_template, jsonify, request
import json
import os
import aiohttp
import asyncio
import ssl
from dotenv import load_dotenv
from flask_cors import CORS
import logging
import jwt
from datetime import datetime

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
load_dotenv()

async def get_tensor_nfts(limit=50, specific_nft=None):
    """Получает данные NFT из Tensor API"""
    try:
        tensor_api_key = os.getenv("TENSOR_API_KEY")
        if not tensor_api_key:
            logger.error("TENSOR_API_KEY not found in environment variables")
            return {"error": "TENSOR_API_KEY not found in environment variables"}
            
        url = "https://api.mainnet.tensordev.io/api/v1/mint/active_listings"
        params = {
            "collId": "3c2450f3-75cf-4327-b927-d7cdc94cef7f",
            "sortBy": "ListingPriceAsc",
            "limit": limit,
            "includePrivateTaker": "false"
        }
        
        # Если указан конкретный NFT, добавляем его в параметры поиска
        if specific_nft:
            params["search"] = f"Defi Dungeons #{specific_nft}"
        
        headers = {
            "accept": "application/json",
            "x-tensor-api-key": tensor_api_key
        }
        
        print(f"\nMaking request to Tensor API:")
        print(f"URL: {url}")
        print(f"Params: {params}")
        print(f"Headers: {headers}")
        
        # Создаем SSL-контекст, который игнорирует проверку сертификата
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, ssl=ssl_context) as response:
                print(f"Response status: {response.status}")
                print(f"Response headers: {response.headers}")
                
                if response.status != 200:
                    return {"error": f"Ошибка при получении данных NFT: {response.status}"}
                    
                data = await response.json()
                print(f"Response data type: {type(data)}")
                print(f"Response data: {data}")
                
                # Обрабатываем данные NFT
                processed_nfts = []
                for nft in data.get("mints", []):
                    # Извлекаем номер NFT из поля name
                    name = nft.get("name", "")
                    nft_number = None
                    if name.startswith("Defi Dungeons #"):
                        try:
                            nft_number = int(name.split("#")[1])
                        except (ValueError, IndexError):
                            continue
                    
                    if nft_number is not None:
                        processed_nft = {
                            "name": name,
                            "nft_number": nft_number,
                            "price_sol": float(nft.get("listing", {}).get("price", 0)) / 1e9,
                            "attributes": nft.get("attributes", []),
                            "image": nft.get("imageUri", "")
                        }
                        processed_nfts.append(processed_nft)
                
                print(f"Processed Tensor NFTs: {processed_nfts}")
                return {"tensor_nfts": processed_nfts}
    except Exception as e:
        print(f"Error in get_tensor_nfts: {str(e)}")
        return {"error": f"Неожиданная ошибка: {str(e)}"}

def is_token_expired(token):
    """Проверяет, не истек ли срок действия токена"""
    try:
        # Декодируем токен без проверки подписи, так как нам нужно только проверить срок действия
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded.get('exp')
        if not exp:
            return False  # Если нет поля exp, считаем что токен не имеет срока действия
            
        # Преобразуем Unix timestamp в datetime
        expiration_time = datetime.fromtimestamp(exp)
        current_time = datetime.now()
        
        # Проверяем, не истек ли токен
        return current_time > expiration_time
    except jwt.InvalidTokenError:
        return True  # Если токен невалидный, считаем что он истек
    except Exception as e:
        print(f"Error checking token expiration: {str(e)}")
        return True

async def get_game_nft_data(nft_number, wallet_address):
    """Получает данные NFT из API игры"""
    try:
        api_token = os.getenv("API_TOKEN")
        if not api_token:
            return {"error": "API credentials not found in environment variables"}
            
        # Проверяем срок действия токена
        if is_token_expired(api_token):
            return {"error": "Токен авторизации истек. Пожалуйста, обновите токен."}
            
        base_url = os.getenv("API_BASE_URL")
        if not base_url:
            return {"error": "API credentials not found in environment variables"}
            
        url = f"{base_url}/marketplace/nfts"
        params = {
            "limit": 20,
            "offset": 0,
            "enabled": "true",
            "sort": "price-asc",
            "search": f"Defi Dungeons #{nft_number}"
        }
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "sec-ch-ua-platform": "\"macOS\"",
            "Referer": "https://dungeons.game/",
            "sec-ch-ua": "\"Chromium\";v=\"134\", \"Not:A-Brand\";v=\"24\", \"Google Chrome\";v=\"134\"",
            "sec-ch-ua-mobile": "?0",
            "Accept": "application/json, text/plain, */*",
            "x-selected-wallet-address": wallet_address
        }
        
        print(f"\nMaking request to game API:")
        print(f"URL: {url}")
        print(f"Params: {params}")
        print(f"Headers: {headers}")
        
        # Создаем SSL-контекст, который игнорирует проверку сертификата
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, ssl=ssl_context) as response:
                print(f"Response status: {response.status}")
                print(f"Response headers: {response.headers}")
                
                if response.status == 401:
                    return {"error": "Ошибка авторизации в игре. Проверьте API токен."}
                    
                if response.status == 403:
                    return {"error": "Доступ запрещен. Проверьте права доступа токена."}
                    
                if response.status != 200:
                    return {"error": f"Ошибка при получении данных NFT: {response.status}"}
                    
                data = await response.json()
                print(f"Response data type: {type(data)}")
                print(f"Response data: {data}")
                
                if response.status == 200 and isinstance(data, list) and len(data) > 0:
                    # Проверяем, что найденная NFT точно соответствует номеру
                    for nft in data:
                        if nft.get("name") == f"Defi Dungeons #{nft_number}":
                            print(f"Found exact NFT match: {nft}")
                            return nft
                    print(f"No exact match found for NFT #{nft_number}")
                    return None
                return None
    except Exception as e:
        print(f"Error in get_game_nft_data: {str(e)}")
        print(f"Error type: {type(e)}")
        return None

async def process_nft_data(tensor_data, wallet_address):
    """Обрабатывает данные NFT"""
    try:
        print("\n=== Processing NFT Data ===")
        print(f"Input tensor_data: {tensor_data}")
        
        processed_nfts = []
        for nft in tensor_data.get("tensor_nfts", []):
            print(f"\nProcessing NFT: {nft}")
            nft_number = nft.get("nft_number")
            if nft_number:
                print(f"Getting game data for NFT #{nft_number}")
                game_data = await get_game_nft_data(nft_number, wallet_address)
                print(f"Game data for NFT #{nft_number}: {game_data}")
                
                if game_data:
                    # Получаем класс из атрибутов Tensor
                    class_from_attributes = None
                    for attr in nft.get("attributes", []):
                        if attr.get("trait_type") == "Class":
                            class_from_attributes = attr.get("value")
                            break
                    
                    processed_nft = {
                        "number": nft_number,
                        "name": nft.get("name", f"Defi Dungeons #{nft_number}"),
                        "class": class_from_attributes or game_data.get("class"),
                        "price_sol": nft.get("price_sol"),
                        "combat": game_data.get("combat", 1),
                        "has_items": len(game_data.get("items", [])) > 0,
                        "image": nft.get("image", "")
                    }
                    print(f"Processed NFT: {processed_nft}")
                    processed_nfts.append(processed_nft)
                else:
                    print(f"No game data found for NFT #{nft_number}")
            else:
                print(f"No NFT number found in: {nft}")
        
        print(f"\nFinal processed NFTs: {processed_nfts}")
        return processed_nfts
    except Exception as e:
        print(f"Error in process_nft_data: {str(e)}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/nfts')
def get_nfts():
    try:
        print("\n=== Starting /api/nfts request ===")
        
        # Получаем параметры из запроса
        limit = request.args.get('limit', default=50, type=int)
        api_token = request.args.get('api_token', default='')
        wallet_address = request.args.get('wallet_address', default='')
        hide_combat1 = request.args.get('hide_combat1', default='false') == 'true'
        nft_number = request.args.get('nft_number', default=None, type=int)
        
        if not wallet_address:
            return jsonify({"error": "Адрес кошелька не указан"}), 400
        
        # Если передан новый токен, обновляем его
        if api_token:
            os.environ['API_TOKEN'] = api_token
        
        # Создаем новый event loop для асинхронного запроса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Выполняем асинхронный запрос
        print("Getting tensor data...")
        tensor_data = loop.run_until_complete(get_tensor_nfts(limit))
        print(f"Tensor data received: {tensor_data}")
        
        # Обрабатываем данные
        print("Processing NFT data...")
        processed_data = loop.run_until_complete(process_nft_data(tensor_data, wallet_address))
        print(f"Processed data: {processed_data}")
        
        # Если указан конкретный номер NFT, фильтруем по нему
        if nft_number is not None:
            processed_data = [nft for nft in processed_data if nft.get('number') == nft_number]
        
        # Фильтруем NFT с Combat 1, если нужно
        if hide_combat1:
            processed_data = [nft for nft in processed_data if nft.get('combat', 1) > 1]
        
        # Закрываем loop
        loop.close()
        
        if "error" in processed_data:
            print(f"Error in processed data: {processed_data}")
            return jsonify(processed_data), 401 if "авторизации" in processed_data["error"] else 500
        
        # Если ищем конкретную NFT, возвращаем все найденные
        if nft_number is not None:
            return jsonify({"nfts": processed_data, "has_more": False, "remaining": []})
        
        # Отправляем первый NFT сразу
        if processed_data:
            return jsonify({"nfts": [processed_data[0]], "has_more": len(processed_data) > 1, "remaining": processed_data[1:]})
        return jsonify({"nfts": [], "has_more": False, "remaining": []})
    except Exception as e:
        print(f"Error in get_nfts: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/nfts/next')
def get_next_nft():
    try:
        remaining_nfts = request.args.getlist('remaining[]')
        if not remaining_nfts:
            return jsonify({"nfts": [], "has_more": False, "remaining": []})
            
        # Преобразуем строки обратно в словари
        remaining = [json.loads(nft) for nft in remaining_nfts]
        
        if remaining:
            return jsonify({
                "nfts": [remaining[0]], 
                "has_more": len(remaining) > 1, 
                "remaining": remaining[1:]
            })
        return jsonify({"nfts": [], "has_more": False, "remaining": []})
    except Exception as e:
        print(f"Error in get_next_nft: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/user/info')
def get_user_info():
    try:
        api_token = request.args.get('api_token')
        wallet_address = request.args.get('wallet_address')
        
        if not api_token:
            return jsonify({'error': 'API token is required'}), 400
            
        if not wallet_address:
            return jsonify({'error': 'Wallet address is required'}), 400
            
        # Создаем новый event loop для асинхронного запроса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Выполняем асинхронный запрос
        user_data = loop.run_until_complete(get_user_data(api_token, wallet_address))
        
        # Закрываем loop
        loop.close()
        
        if "error" in user_data:
            return jsonify(user_data), 401 if "авторизации" in user_data["error"] else 500
            
        return jsonify(user_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

async def get_user_data(api_token, wallet_address):
    """Получает данные пользователя из API игры"""
    try:
        # Проверяем срок действия токена
        if is_token_expired(api_token):
            return {"error": "Токен авторизации истек. Пожалуйста, обновите токен."}
            
        base_url = os.getenv("API_BASE_URL")
        if not base_url:
            return {"error": "API_BASE_URL not found in environment variables"}
            
        url = f"{base_url}/user/me"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "x-selected-wallet-address": wallet_address
        }
        
        print(f"\n=== User Info Request ===")
        print(f"URL: {url}")
        print(f"Headers: {headers}")
        
        # Создаем SSL-контекст, который игнорирует проверку сертификата
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=ssl_context) as response:
                print(f"Response status: {response.status}")
                
                if response.status == 401:
                    return {"error": "Ошибка авторизации в игре. Проверьте API токен."}
                    
                if response.status != 200:
                    return {"error": f"Ошибка при получении данных пользователя: {response.status}"}
                    
                data = await response.json()
                print(f"Response data: {data}")
                
                # Проверяем наличие всех необходимых полей
                if not data.get("wallet"):
                    return {"error": "Данные пользователя не содержат информацию о кошельке"}
                
                # Получаем личный реферальный код пользователя
                referral_code = data["wallet"]['referral'].get("referralCode")
                if not referral_code:
                    return {"error": "Реферальный код не найден"}
                
                return {
                    "referral_code": referral_code
                }
    except aiohttp.ClientError as e:
        print(f"Network error: {str(e)}")
        return {"error": f"Ошибка сети: {str(e)}"}
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {str(e)}")
        return {"error": "Ошибка при обработке ответа от сервера"}
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return {"error": f"Неожиданная ошибка: {str(e)}"}

@app.route('/api/nft/check')
def check_nft():
    try:
        nft_number = request.args.get('nft_number', type=int)
        api_token = request.args.get('api_token', default='')
        wallet_address = request.args.get('wallet_address', default='')
        
        if not nft_number:
            return jsonify({"error": "Номер NFT не указан"}), 400
            
        if not wallet_address:
            return jsonify({"error": "Адрес кошелька не указан"}), 400
        
        # Если передан новый токен, обновляем его
        if api_token:
            os.environ['API_TOKEN'] = api_token
        
        # Создаем новый event loop для асинхронного запроса
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Получаем данные NFT напрямую из API игры
        game_data = loop.run_until_complete(get_game_nft_data(nft_number, wallet_address))
        
        # Получаем данные о цене из Tensor API
        tensor_data = loop.run_until_complete(get_tensor_nfts(1, nft_number))
        
        # Закрываем loop
        loop.close()
        
        if isinstance(game_data, dict) and "error" in game_data:
            return jsonify(game_data), 401 if "авторизации" in game_data["error"] else 500
            
        if not game_data:
            return jsonify({"error": "NFT не найден"}), 404
        
        # Получаем цену из Tensor данных
        price_sol = None
        if tensor_data and "tensor_nfts" in tensor_data and tensor_data["tensor_nfts"]:
            price_sol = tensor_data["tensor_nfts"][0].get("price_sol")
        
        # Формируем ответ
        result = {
            "number": nft_number,
            "name": game_data.get("name", f"Defi Dungeons #{nft_number}"),
            "class": game_data.get("class"),
            "price_sol": price_sol,
            "combat": game_data.get("combat", 1),
            "has_items": len(game_data.get("items", [])) > 0,
            "image": game_data.get("image", ""),
            "stats": {
                stat["statType"]: stat["value"] 
                for stat in game_data.get("nftStats", [])
            },
            "traits": [
                {"type": trait["type"], "value": trait["value"]}
                for trait in game_data.get("traits", [])
            ],
            "items": [
                {
                    "name": item["itemMetadata"]["name"],
                    "type": item["itemMetadata"]["type"],
                    "level": item["itemMetadata"]["level"],
                    "rarity": item["itemMetadata"]["rarity"],
                    "effects": item["itemMetadata"]["effects"]
                }
                for item in game_data.get("items", [])
            ]
        }
        
        return jsonify(result)
    except Exception as e:
        print(f"Error in check_nft: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 