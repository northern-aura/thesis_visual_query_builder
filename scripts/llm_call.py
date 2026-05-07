import os
import requests
import base64
import cv2 as cv
import ollama
from ollama import Client

ollama = Client(host="http://host.docker.internal:11434")

def send_to_gpt(img, prompt, examples=[]):
        # Try to read API key from file first
        api = None
        api_key_file = '/scripts/.openai_api_key'

        try:
            with open(api_key_file, 'r') as f:
                api = f.read().strip()
        except:
            # Fallback to environment variable
            api = os.environ.get('OPENAI_API_KEY')

        if not api:
            return "Error: OPENAI_API_KEY environment variable not set", "gpt-4o"

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
            "model": "gpt-4o",
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
            response_json = response.json()

            # Check if the response has the expected structure
            if "choices" in response_json and len(response_json["choices"]) > 0:
                text = response_json["choices"][0]["message"]["content"]
                return text, "gpt-4o"
            else:
                # Handle API error responses
                error_msg = response_json.get("error", {}).get("message", "Unknown error")
                return f"Failed with error: {error_msg}", "gpt-4o"

        except Exception as ex:
            return "Failed with exception: " + str(ex), "gpt-4o"

def send_to_vllm(model, img, prompt, server="http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"):
    _, buffer = cv.imencode('.jpg', img)
    img_as_text = base64.b64encode(buffer).decode("UTF-8")

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_as_text}"}}
                ]
            }
        ],
        "max_tokens": 50,
        "temperature": 0
    }

    try:
        response = requests.post(f"{server}/v1/chat/completions",
                                 headers={"Content-Type": "application/json"},
                                 json=payload)
        response_json = response.json()
        if "choices" in response_json and len(response_json["choices"]) > 0:
            text = response_json["choices"][0]["message"]["content"]
            return text, model
        else:
            error_msg = response_json.get("error", {}).get("message", "Unknown error")
            return f"Failed with error: {error_msg}", model
    except Exception as ex:
        return "Failed with exception: " + str(ex), model

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
    
def send_to_gpt_multi(images, prompt):
    """Send multiple images to GPT-4o in a single API call."""
    api = None
    api_key_file = '/scripts/.openai_api_key'

    try:
        with open(api_key_file, 'r') as f:
            api = f.read().strip()
    except:
        api = os.environ.get('OPENAI_API_KEY')

    if not api:
        return "Error: OPENAI_API_KEY environment variable not set", "gpt-4o"

    content = [{"type": "text", "text": prompt}]
    for img in images:
        _, buffer = cv.imencode('.jpg', img)
        img_b64 = base64.b64encode(buffer).decode("UTF-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api}"
    }

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": content}]
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        response_json = response.json()
        if "choices" in response_json and len(response_json["choices"]) > 0:
            text = response_json["choices"][0]["message"]["content"]
            return text, "gpt-4o"
        else:
            error_msg = response_json.get("error", {}).get("message", "Unknown error")
            return f"Failed with error: {error_msg}", "gpt-4o"
    except Exception as ex:
        return "Failed with exception: " + str(ex), "gpt-4o"

def send_to_ollama_multi(model, images, prompt):
    """Send multiple images to an Ollama model in a single API call."""
    encoded_images = []
    for img in images:
        _, buffer = cv.imencode('.jpg', img)
        encoded_images.append(base64.b64encode(buffer).decode("UTF-8"))

    try:
        response = ollama.chat(
            model=model,
            messages=[
                {"role": "user", "content": prompt, "images": encoded_images}
            ]
        )
        return response["message"]["content"], model
    except Exception as ex:
        return "Failed with exception: " + str(ex), model

def send_to_vllm_multi(model, images, prompt, server="http://dgx01.lab.dm.informatik.tu-darmstadt.de:8000"):
    """Send multiple images to a vLLM model in a single API call."""
    content = [{"type": "text", "text": prompt}]
    for img in images:
        _, buffer = cv.imencode('.jpg', img)
        img_b64 = base64.b64encode(buffer).decode("UTF-8")
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 50,
        "temperature": 0
    }

    try:
        response = requests.post(f"{server}/v1/chat/completions",
                                 headers={"Content-Type": "application/json"},
                                 json=payload)
        response_json = response.json()
        if "choices" in response_json and len(response_json["choices"]) > 0:
            text = response_json["choices"][0]["message"]["content"]
            return text, model
        else:
            error_msg = response_json.get("error", {}).get("message", "Unknown error")
            return f"Failed with error: {error_msg}", model
    except Exception as ex:
        return "Failed with exception: " + str(ex), model

def prompt_llm(img, prompt, examples=[]):
    #return send_to_gpt(img, prompt, examples)
    
    #return send_to_ollama("llava", img, prompt, examples)
    #return send_to_ollama("bakllava", img, prompt, examples) # Poor results
    #return send_to_ollama("llava-llama3", img, prompt, examples)
    # return send_to_ollama("gemma3:4b", img, prompt, examples)
    return send_to_gpt(img, prompt, examples)
    #return send_to_ollama("llama3.2-vision", img, prompt, examples)
    
    #return send_to_ollama("mistral-small3.1", img, prompt, examples) # Min 14.5G Memory
    
    
    
    
    