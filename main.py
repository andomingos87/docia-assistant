from fastapi import FastAPI, Request
import json

app = FastAPI()

@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    
    # Extraia os dados relevantes
    sender = data.get('sender')
    message = data.get('message')
    
    # Exemplo de processamento: imprimir no console
    print(f"Mensagem recebida de {sender}: {message}")
    
    return {"status": "mensagem recebida!"}