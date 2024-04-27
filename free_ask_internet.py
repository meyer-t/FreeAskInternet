# -*- coding: utf-8 -*-

import json
import os 
from pprint import pprint
import requests
import trafilatura
from trafilatura import bare_extraction
from concurrent.futures import ThreadPoolExecutor
import concurrent
import requests
import openai
import time 
from datetime import datetime
from urllib.parse import urlparse
import tldextract
import platform
import urllib.parse

 
def extract_url_content(url):
    downloaded = trafilatura.fetch_url(url)
    content =  trafilatura.extract(downloaded)
    
    return {"url":url, "content":content}


 

def search_web_ref(query:str, debug=False):
 
    content_list = []

    try:

        safe_string = urllib.parse.quote_plus(":all !general " + query)

        response = requests.get('http://searxng:8080?q=' + safe_string + '&format=json')
        response.raise_for_status()
        search_results = response.json()
 
        if debug:
            print("JSON Response:")
            pprint(search_results)
        pedding_urls = []

        conv_links = []

        if search_results.get('results'):
            for item in search_results.get('results')[0:9]:
                name = item.get('title')
                snippet = item.get('content')
                url = item.get('url')
                pedding_urls.append(url)

                if url:
                    url_parsed = urlparse(url)
                    domain = url_parsed.netloc
                    icon_url =  url_parsed.scheme + '://' + url_parsed.netloc + '/favicon.ico'
                    site_name = tldextract.extract(url).domain
 
                conv_links.append({
                    'site_name':site_name,
                    'icon_url':icon_url,
                    'title':name,
                    'url':url,
                    'snippet':snippet
                })

            results = []
            futures = []

            executor = ThreadPoolExecutor(max_workers=10) 
            for url in pedding_urls:
                futures.append(executor.submit(extract_url_content,url))
            try:
                for future in futures:
                    res = future.result(timeout=5)
                    results.append(res)
            except concurrent.futures.TimeoutError:
                print("Timeout")
                executor.shutdown(wait=False,cancel_futures=True)

            for content in results:
                if content and content.get('content'):
                    
                    item_dict = {
                        "url":content.get('url'),
                        "content": content.get('content'),
                        "length":len(content.get('content'))
                    }
                    content_list.append(item_dict)
                if debug:
                    print("URL: {}".format(url))
                    print("=================")
 
        return  conv_links,content_list
    except Exception as ex:
        raise ex


def gen_prompt(question,content_list, lang="de_DE", context_length_limit=11000,debug=False):
    
    limit_len = (context_length_limit - 2000)
    if len(question) > limit_len:
        question = question[0:limit_len]
    
    ref_content = [ item.get("content") for item in content_list]
    
    answer_language = ' German '
    if lang == "de-DE":
        answer_language = ' German '
    if lang == "zh-TW":
        answer_language = ' Traditional Chinese '
    if lang == "en-US":
        answer_language = ' English '


    if len(ref_content) > 0:
        
        if False:
            prompts = '''
            Sie sind ein von mir entwickelter KI-Assistent für große Sprachen. Sie erhalten eine Benutzerfrage und werden gebeten, eine klare, prägnante und genaue Antwort zu verfassen. Stellt eine Reihe von Kontexten bereit, die für die Frage relevant sind und jeweils mit einer Zahl beginnen, z. B. [[citation:x]], wobei x eine Zahl darstellt. Bitte zitieren Sie ggf. den Kontext am Ende des Satzes. Die Antworten müssen korrekt und präzise sein und im neutralen und professionellen Ton eines Experten verfasst sein. Bitte beschränken Sie die Antworten auf 2000 Token. Geben Sie keine Informationen an, die für die Frage nicht relevant sind, und wiederholen Sie diese nicht. Wenn nicht genügend Kontextinformationen angegeben sind, schreiben Sie „Informationen fehlen:“ nach dem entsprechenden Thema. Bitte geben Sie den Kontext im entsprechenden Teil Ihrer Antwort im Format der Zitatnummer [Citation:x] an. Wenn ein Satz aus mehreren Kontexten stammt, listen Sie alle relevanten Zitatnummern auf, zum Beispiel [Citation:3][Citation:5]. Geben Sie die Zitate nicht zusammen am Ende zurück, sondern listen Sie sie im entsprechenden Teil der Antwort auf. Sofern es sich nicht um einen Code, einen bestimmten Namen oder eine Referenznummer handelt, sollte die Antwort in derselben Sprache wie die Frage verfasst sein. Das Folgende ist der Inhaltssatz des Kontexts：
            '''  + "\n\n" + "```" 
            ref_index = 1

            for ref_text in ref_content:
                
                prompts = prompts + "\n\n" + " [citation:{}]  ".format(str(ref_index)) +  ref_text
                ref_index += 1

            if len(prompts) >= limit_len:
                prompts = prompts[0:limit_len]        
            prompts = prompts + '''
    ```
    Denken Sie daran, den Kontext nicht wörtlich zu wiederholen. Wenn die Antwort lang ist, versuchen Sie bitte, sie in Absätzen zu strukturieren. Bitte geben Sie den Kontext im entsprechenden Teil Ihrer Antwort im Format der Zitatnummer [citation:x] an. Wenn ein Satz aus mehreren Kontexten stammt, listen Sie alle relevanten Zitatnummern auf, zum Beispiel [citation:3][citation:5]. Geben Sie die Zitate nicht zusammen am Ende zurück, sondern listen Sie sie im entsprechenden Teil der Antwort auf. Hier sind die Benutzerfragen：
    ''' + question  
        else:
            prompts = '''
            You are a large language AI assistant develop by nash_su. You are given a user question, and please write clean, concise and accurate answer to the question. You will be given a set of related contexts to the question, each starting with a reference number like [[citation:x]], where x is a number. Please use the context and cite the context at the end of each sentence if applicable.
            Your answer must be correct, accurate and written by an expert using an unbiased and professional tone. Please limit to 1024 tokens. Do not give any information that is not related to the question, and do not repeat. Say "information is missing on" followed by the related topic, if the given context do not provide sufficient information.

            Please cite the contexts with the reference numbers, in the format [citation:x]. If a sentence comes from multiple contexts, please list all applicable citations, like [citation:3][citation:5]. Other than code and specific names and citations, your answer must be written in the same language as the question.
            Here are the set of contexts:
            '''  + "\n\n" + "```" 
            ref_index = 1

            for ref_text in ref_content:
                
                prompts = prompts + "\n\n" + " [citation:{}]  ".format(str(ref_index)) +  ref_text
                ref_index += 1

            if len(prompts) >= limit_len:
                prompts = prompts[0:limit_len]        
            prompts = prompts + '''
            ```
            Above is the reference contexts. Remember, don't repeat the context word for word. Answer in ''' + answer_language + '''. If the response is lengthy, structure it in paragraphs and summarize where possible. Cite the context using the format [citation:x] where x is the reference number. If a sentence originates from multiple contexts, list all relevant citation numbers, like [citation:3][citation:5]. Don't cluster the citations at the end but include them in the answer where they correspond.
            Remember, don't blindly repeat the contexts verbatim. And here is the user question:
            ''' + question  
 
     
    else:
        prompts = question

    if debug:
        print(prompts)
        print("Gesamtlänge："+ str(len(prompts)))
    return prompts


def chat(prompt, model:str,llm_auth_token:str,llm_base_url:str,using_custom_llm=False,stream=True, debug=False):
    openai.base_url = "http://127.0.0.1:3040/v1/"

    if model == "gpt3.5":
        openai.base_url = "http://llm-freegpt35:3040/v1/"
    
    if model == "kimi":
        openai.base_url = "http://llm-kimi:8000/v1/"
    if model == "glm4":
        openai.base_url = "http://llm-glm4:8000/v1/"
    if model == "qwen":
        openai.base_url = "http://llm-qwen:8000/v1/"
    

    if llm_auth_token == '':
        llm_auth_token = "CUSTOM"
        
    openai.api_key = llm_auth_token

    if using_custom_llm:
        openai.base_url = llm_base_url
        openai.api_key = llm_auth_token


    total_content = ""
    for chunk in openai.chat.completions.create(
        model=model,
        messages=[{
            "role": "user",
            "content": prompt
        }],
        stream=True,
        max_tokens=1024,temperature=0.2
    ):
        stream_resp = chunk.dict()
        token = stream_resp["choices"][0]["delta"].get("content", "")
        if token:
            
            total_content += token
            yield token
    if debug:
        print(total_content)
 

 
    
def ask_internet(query:str,  debug=False):
  
    content_list = search_web_ref(query,debug=debug)
    if debug:
        print(content_list)
    prompt = gen_prompt(query,content_list,context_length_limit=6000,debug=debug)
    total_token =  ""
 
    for token in chat(prompt=prompt):
    # for token in daxianggpt.chat(prompt=prompt):
        if token:
            total_token += token
            yield token
    yield "\n\n"
    # Ob zu Referenzmaterialien zurückgekehrt werden soll
    if True:
        yield "---"
        yield "\n"
        yield "Quellen:\n"
        count = 1
        for url_content in content_list:
            url = url_content.get('url')
            yield "*[{}. {}]({})*".format(str(count),url,url )  
            yield "\n"
            count += 1
 
