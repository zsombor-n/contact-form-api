import os
import arrow

from typing import List
from pydantic import Field

import smtplib, ssl
from email.message import EmailMessage

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic_settings import BaseSettings
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import uvicorn

load_dotenv()

# Khởi tạo FastAPI
app = FastAPI(
    title="Contact Form API",
    description="This is FastAPI-based API is designed for submitting contact forms and receiving notifications.",
    version="1.0.3",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    terms_of_service="https://nguyenhongthe.net/tos/",
    contact={
        "name": "Nguyen Hong The",
        "url": "https://nguyenhongthe.dev/contact/",
        "email": "hello@nguyenhongthe.dev",
    },
    license_info={
        "name": "MIT License",
        "url": "https://nguyenhongthe.net/license/"
    },
)

# Cấu hình chung
class Settings(BaseSettings):
    postgres_url: str
    discord_webhook_url: str
    email_subject: str
    sender_name: str
    sender_email: str
    recipient_name: str
    recipient_email: str
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    origins_urls: List[str] = Field(default_factory=list)

config = Settings()

# Thiết lập CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.origins_urls,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Thiết lập kết nối tới cơ sở dữ liệu PostgreSQL
engine = create_engine(config.postgres_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Lấy thời gian hiện tại theo múi giờ Asia/Ho_Chi_Minh
timestamp = arrow.utcnow().to('Asia/Ho_Chi_Minh').format('YYYY-MM-DD HH:mm:ss')

class ContactForm(Base):
    """
    Định nghĩa bảng dữ liệu contact_forms
    """
    __tablename__ = "contact_forms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, index=True)
    phone = Column(String, index=True)
    title = Column(String, index=True)
    message = Column(String, index=True)
    created_at = Column(String, index=True, default=timestamp)

Base.metadata.create_all(bind=engine)

def send_email(config, send_message, name, email):
    """
    Gửi email thông báo
    """
    msg = EmailMessage()
    msg['Subject'] = config.email_subject
    msg['From'] = f"{config.sender_name} <{config.sender_email}>"
    msg['To'] = f"{config.recipient_name} <{config.recipient_email}>"
    msg['Reply-To'] = f"{name} <{email}>"
    msg.set_content(send_message)

    try:
        if config.smtp_port == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port, context=context) as server:
                server.login(config.smtp_username, config.smtp_password)
                server.send_message(msg)
        elif config.smtp_port == 587:
            with smtplib.SMTP(config.smtp_server, config.smtp_port) as server:
                server.starttls()
                server.login(config.smtp_username, config.smtp_password)
                server.send_message(msg)
        else:
            print("Use 465 / 587 as port value")
            return
        print("Successfully sent email")
    except Exception as e:
        print(f"Failed to send email: {e}")

async def send_discord_notification(config, message):
    """
    Gửi thông báo tới Discord
    """
    webhook_url = config.discord_webhook_url
    payload = {"content": message}
    async with httpx.AsyncClient() as client:
        response = await client.post(webhook_url, json=payload)
        if response.status_code == 204:
            print("Successfully sent notification to Discord")
        else:
            print(f"Failed to send notification to Discord: {response.status_code}")

def save_to_postgresql(name, email, phone, title, message):
    """
    Lưu dữ liệu vào PostgreSQL
    """
    session = SessionLocal()
    contact_form = ContactForm(name=name, email=email, phone=phone, title=title, message=message, created_at=timestamp)
    session.add(contact_form)
    session.commit()
    session.close()

@app.get("/")
async def root():
    """
    fake root
    """
    return {"message": "Hello World"}

@app.get("/api")
async def api():
    """
    fake api
    """
    return {"message": "Hello API"}

@app.post("/submit_contact_form")
async def submit_contact_form(
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    title: str = Form(...),
    message: str = Form(...)
):
    """
    API gửi form liên hệ
    """
    send_message = f"[{config.sender_name}] New contact form submission:\n\n *Time: {timestamp}*\n\n- Name: {name}\n- Email: {email}\n- Phone: {phone}\n- Title: {title}\n- Message:\n\n{message}"
    send_email(config, send_message, name, email)
    await send_discord_notification(config, send_message)
    save_to_postgresql(name, email, phone, title, message)
    return {"message": "Contact form submitted successfully"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
