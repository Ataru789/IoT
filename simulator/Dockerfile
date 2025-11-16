FROM python:3.13.9-slim
WORKDIR /app
RUN pip install --no-cache-dir paho-mqtt
COPY simulator.py /app/simulator.py
CMD ["python", "-u", "simulator.py"]