import streamlit as st
import openai
import requests
from io import BytesIO
from PIL import Image
import os
import boto3
import pymysql

openai.api_key = st.secrets["api_key"]

# aws S3 설정
s3 = boto3.client(
    "s3",
    aws_access_key_id=st.secrets["aws_access_key_id"],
    aws_secret_access_key=st.secrets["aws_secret_access_key"],
    region_name=st.secrets["aws_region_name"]
)

def connect_to_db():
    connection = pymysql.connect(
        host=st.secrets["db_host"],
        user=st.secrets["db_user"],
        password=st.secrets["db_password"],
        database=st.secrets["db_name"],
        port=int(st.secrets["db_port"])
    )
    return connection

st.title("GET /api Module Project1")
if "image_url" not in st.session_state:
    st.session_state.image_url = None


with st.form("form"):
    user_input = st.text_input("Prompt")
    size = st.selectbox("Size", ["1024x1024", "512x512", "256x256"])
    submit = st.form_submit_button("Submit")


if submit and user_input:
    gpt_prompt = [{
        "role": "system",
        "content": "Imagine the detail appeareance of the input. Response it shortly around 20 words"
    }]

    gpt_prompt.append({
        "role": "user",
        "content": user_input
    })

    with st.spinner("Waiting for ChatGPT..."):
        gpt_response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=gpt_prompt
        )

    prompt = gpt_response["choices"][0]["message"]["content"]
    st.write(prompt)

    with st.spinner("Waiting for DALL-E..."):
        dalle_response = openai.Image.create(
            prompt=prompt,
            size=size
        )
        st.session_state.image_url = dalle_response["data"][0]["url"]  # session_state에 저장
        st.image(st.session_state.image_url)  # 이미지 표시

if st.session_state.image_url:
        save = st.button("Save to s3", key="save_button")

        if save:

           Image_data = requests.get(st.session_state.image_url).content

           # BytesIO 객체에 이미지 데이터를 임시저장 
           image = Image.open(BytesIO(Image_data))

           buffer = BytesIO()
           image.save(buffer, format="PNG")
           buffer.seek(0)

           s3_bucket = st.secrets["s3_bucket"]
           s3_key = user_input + ".png"

           # s3에 파일 업로드
           s3.upload_fileobj(buffer, s3_bucket, s3_key)


           #s3_url 생성
           s3_url = f"https://{s3_bucket}.s3.{st.secrets['aws_region_name']}.amazonaws.com/{s3_key}"

           st.success(f"Image uploaded to S3.")


           st.markdown(f'<a href="{s3_url}" style="word-wrap: break-word; white-space: pre-wrap;">Download the image from S3</a>',
                       unsafe_allow_html=True
                      )
           
           with connect_to_db() as connection:
                with connection.cursor() as cursor:
                    sql = "INSERT INTO images (keyword, image_url) VALUES (%s, %s)"
                    cursor.execute(sql, (user_input, s3_url))
                    connection.commit()
                    connection.close()
                st.success("Image data saved to the database.")