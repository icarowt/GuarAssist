"""
GuarAssist Agente
=================
Agente de IA para produtores de guaraná, independente de canal.

    Telegram / WhatsApp / Web  ->  agent.core.processar()  ->  Resposta

O núcleo nunca fala direto com o Telegram. Ele devolve uma Resposta com
texto, imagem anotada e uma lista de ações (alertar vizinhos, agendar retorno).
Quem executa as ações é o adaptador do canal.
"""
