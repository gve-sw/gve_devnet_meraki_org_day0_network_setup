FROM python:3.12-alpine

WORKDIR /app
COPY ./requirements.txt /app
RUN pip install -r requirements.txt
COPY ./src .

CMD ["python", "./setup.py"]
