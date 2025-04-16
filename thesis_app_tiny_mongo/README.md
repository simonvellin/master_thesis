# README.md

## Setup guide

1. **Install Docker**  
   Make sure Docker is installed and running on your machine. You can download it from [https://www.docker.com/get-started](https://www.docker.com/get-started).

2. **(Optional) Install MongoDB Compass**  
   This is a GUI for interacting with your MongoDB database. You can download it from [https://www.mongodb.com/products/compass](https://www.mongodb.com/products/compass).

3. **Create a `.env` File**  
   Duplicate the provided `.env.example` file and rename it to `.env`. Update any necessary environment variables inside it.

4. **Start the Application**  
   From the `thesis_app_tiny_mongo` directory, run the following command to build and start the services:
   ```bash
   docker-compose up --build

5. **Access the app**
   Once the containers are running, open your browser and go to:
   [http://localhost:8501](http://localhost:8501).