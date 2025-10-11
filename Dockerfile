# Base image
FROM python:3.11.7

# Set working directory
WORKDIR /app

# Copy code
COPY . .

# Install dependencies
RUN pip install -r requirements.txt

# Run the app
CMD ["python", "app.py"]
