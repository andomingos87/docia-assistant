from fastapi import FastAPI, Request
from dotenv import load_dotenv
import requests
import json
import urllib.parse
import os
import time

load_dotenv()

app = FastAPI()

def normalize_number(number):
    return number.replace("+", "").replace(" ", "").strip()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BUBBLE_API_KEY = os.environ.get("BUBBLE_API_KEY")

@app.post("/webhook")   
async def receive_message(request: Request):
    # Extrair informações do corpo da requisição
    data = await request.json()
    sender = data.get("sender")
    message = data.get("message")
    
    # Definir URL e cabeçalhos para interagir com a API do Bubble
    bubble_api_url = "https://docia-16751.bubbleapps.io/version-test/api/1.1/obj/user"
    headers = {
        "Authorization": f"Bearer {BUBBLE_API_KEY}",
        "Content-Type": "application/json",
    }

    # Configurar os critérios de consulta para buscar o número no banco de dados do Bubble
    constraints = [
        {
            "key": "whatsapp",
            "constraint_type": "equals",
            "value": sender
        }
    ]
    constraints_param = json.dumps(constraints)
    encoded_constraints = urllib.parse.quote_plus(constraints_param)

    # Fazer uma requisição GET para buscar informações do usuário no Bubble
    response = requests.get(f"{bubble_api_url}?constraints={encoded_constraints}", headers=headers)

    # Verificar se a resposta da API foi bem-sucedida
    if response.status_code == 200:
        bubble_data = response.json()

        # Procurar o número no banco de dados
        results = bubble_data.get("response", {}).get("results", [])
        number_found = False
        for record in results:
            db_number = normalize_number(record.get("whatsapp", ""))
            sender_normalized = normalize_number(sender)
            if db_number == sender_normalized:
                number_found = True
                break

        # Se o número for encontrado, retorne o sucesso
        if number_found:
            print("O número existe, aguarde...")
            return {"status": "Número encontrado no banco de dados", "data": record}
        else:
            # Caso o número não seja encontrado, iniciar uma nova conversa com o OpenAI
            try:
                openai_api_url = "https://api.openai.com/v1/threads"
                openai_headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "OpenAI-Beta": "assistants=v2"
                }
                thread_payload = {}  # Parâmetros adicionais, se necessário

                # Criar uma nova thread de conversa na API do OpenAI
                thread_response = requests.post(openai_api_url, headers=openai_headers, json=thread_payload)

                # Verificar se a criação da thread foi bem-sucedida
                if thread_response.status_code == 200:
                    thread_data = thread_response.json()
                    thread_id = thread_data['id']  # Obter o ID da thread criada
                    print(f"Thread criada com ID: {thread_id}")

                    # Enviar mensagem na thread criada
                    message_url = f"https://api.openai.com/v1/threads/{thread_id}/messages"
                    message_payload = {
                        "role": "user",
                        "content": message
                    }

                    message_response = requests.post(message_url, headers=openai_headers, json=message_payload)

                    # Verificar se a mensagem foi enviada com sucesso
                    if message_response.status_code == 200:
                        print(f"Mensagem enviada com sucesso para a thread {thread_id}")

                        # Criar uma execução (run) na thread existente
                        run_url = f"https://api.openai.com/v1/threads/{thread_id}/runs"
                        run_payload = {
                            "assistant_id": "asst_V7Anhdufy2xwvmRHCCsZRBiK"  # ID do assistente desejado
                        }

                        run_response = requests.post(run_url, headers=openai_headers, json=run_payload)

                        # Verificar se a criação da run foi bem-sucedida
                        if run_response.status_code == 200:
                            run_data = run_response.json()
                            run_id = run_data['id']
                            print(f"Run criada com ID: {run_id}")

                            # Aguardar a conclusão da run com timeout
                            run_status_url = f"https://api.openai.com/v1/threads/{thread_id}/runs/{run_id}"
                            max_attempts = 30  # Limite de tentativas para evitar loop infinito
                            attempts = 0

                            while attempts < max_attempts:
                                status_response = requests.get(run_status_url, headers=openai_headers)
                                if status_response.status_code == 200:
                                    status_data = status_response.json()
                                    status = status_data.get('status')
                                    if status == 'succeeded':
                                        # Run concluída com sucesso
                                        print("Obtendo resposta do GPT...")
                                        assistant_reply = status_data.get('result', {}).get('message', {}).get('content')
                                        if assistant_reply:
                                            print(f"Resposta do GPT (succeeded): {assistant_reply}")
                                            # Enviar a resposta de volta ao usuário via WhatsApp
                                            send_whatsapp_message(sender, assistant_reply)
                                            return {"status": "Conversa iniciada", "reply": assistant_reply}
                                        else:
                                            print("Não foi possível obter a resposta do assistente.")
                                            return {"status": "Erro ao obter a resposta do assistente"}
                                    elif status == 'failed':
                                        print("A run falhou.")
                                        return {"status": "Erro: a run falhou."}
                                    else:
                                        # Aguardando a conclusão da run
                                        print(f"Status da run: {status}. Aguardando...")
                                        time.sleep(1)  # Aguarda 1 segundo antes de verificar novamente
                                        attempts += 1
                                else:
                                    print(f"Erro ao verificar o status da run: {status_response.text}")
                                    return {"status": f"Erro ao verificar o status da run: {status_response.text}"}

                            # Se o tempo limite for atingido
                            print("Tempo limite atingido ao aguardar a conclusão da run.")
                            return {"status": "Erro: tempo limite atingido ao aguardar a conclusão da run."}
                        else:
                            print(f"Erro ao criar run: {run_response.text}")
                            return {"status": f"Erro ao criar run: {run_response.text}"}
                    else:
                        print(f"Erro ao enviar mensagem: {message_response.text}")
                        return {"status": f"Erro ao enviar mensagem: {message_response.text}"}
                else:
                    print(f"Erro ao criar thread: {thread_response.text}")
                    return {"status": f"Erro ao criar thread: {thread_response.text}"}
            except Exception as e:
                print(f"Erro ao interagir com a API da OpenAI: {e}")
                return {"status": f"Erro ao interagir com a API da OpenAI: {e}"}
    else:
        return {"status": f"Erro ao acessar o banco de dados: {response.text}"}

# Função para enviar uma mensagem via WhatsApp (a ser implementada)
def send_whatsapp_message(to_number, message_text):
    # Implemente aqui a lógica para enviar a mensagem via WhatsApp
    print(f"Enviando mensagem para {to_number}: {message_text}")
    pass
