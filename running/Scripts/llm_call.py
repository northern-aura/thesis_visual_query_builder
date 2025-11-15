import requests
import base64 
import cv2 as cv
import ollama
from ollama import Client

#ollama.base_url = "http://host.docker.internal:11434"

ollama = Client(host="http://host.docker.internal:11434")

def send_to_gpt(img, prompt, examples=[]):
        api = "YOUR API KEY"

        # Complete chat for given examples
        example_chat = []

        if len(examples) != 0:
            for i in range(len(examples)):
                example_chat.append({
                    "role": "user",
                    "content": [
                        {
                        "type": "text",
                        "text": f"{prompt}"
                        },
                        {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{examples[i][0]}"
                        }
                        }
                    ]
                })
                example_chat.append({
                    "role": "assistant",
                    "content": f"{str(examples[i][1])}"
                })

        # Convert the frame to b64
        _, buffer = cv.imencode('.jpg', img)
        img_as_text = base64.b64encode(buffer).decode("UTF-8")

        headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api}"
        }

        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                *example_chat,
                {
                    "role": "user",
                    "content": [
                        {
                        "type": "text",
                        "text": f"{prompt}"
                        },
                        {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{img_as_text}"
                        }
                        }
                    ]
                }
            ]
            #"max_tokens": 50
        }

        try:
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            return response.json()["choices"][0]["message"]["content"], "gpt-4o-mini"

        except Exception as ex:
            return "Failed with exception: " + str(ex), "gpt-4o-mini"

def send_to_ollama(model, img, prompt, examples=[]):
    
    # Complete chat for given examples
    example_chat = []

    if len(examples) != 0:
        for i in range(len(examples)):
            example_chat.append({"role" : "user", "content" : prompt, "images" : [examples[i][0]]})
            example_chat.append({"role" : "assistant", "content" : str(examples[i][1])})

    # Encode the image to b64
    _, buffer = cv.imencode('.jpg', img)
    img_as_text = base64.b64encode(buffer).decode("UTF-8")

    # Send the frame to llava and catch any exception
    try:
        response = ollama.chat(
            model=model,
            messages=[
                *example_chat,
                {"role" : "user", "content" : prompt, "images" : [img_as_text]},
            ]
        )
        return response["message"]["content"], model
    
    except Exception as ex:
        return "Failed with exception: " + str(ex), model
    
def prompt_llm(img, prompt, examples=[]):
    #return send_to_gpt(img, prompt, examples)
    
    #return send_to_ollama("llava", img, prompt, examples)
    #return send_to_ollama("bakllava", img, prompt, examples) # Poor results
    #return send_to_ollama("llava-llama3", img, prompt, examples)
    return send_to_ollama("gemma3:4b", img, prompt, examples)
    #return send_to_ollama("llama3.2-vision", img, prompt, examples)
    
    #return send_to_ollama("mistral-small3.1", img, prompt, examples) # Min 14.5G Memory
    
    
    
    
    