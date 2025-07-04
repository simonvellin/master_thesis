<h1 align="center">Master Thesis</h1>
<h2 align="center">German Federal Foreign Office Challenge</h2>

<p align="center">
  <b>Hannes Schiemann, Simon Vellin, Ferran Boada</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12-blue?logo=python">
  <img src="https://img.shields.io/badge/geopandas-0.14.3-green?logo=python">
  <img src="https://img.shields.io/badge/geopandas-0.14.3-yellow?logo=geopandas">
  <img src="https://img.shields.io/badge/neo4j-5.15.0-critical?logo=neo4j">
  <img src="https://img.shields.io/badge/mongodb-6.0.5-purple?logo=mongodb">
  <img src="https://img.shields.io/badge/streamlit-1.35.0-red?logo=streamlit">
  <img src="https://img.shields.io/badge/docker-20.10.24-gray?logo=docker">
  <img src="https://img.shields.io/badge/docker--compose-2.20.2-lightgray?logo=docker">
</p>

Our thesis focuses on developing an automated tool that generates monthly conflict briefings using structured event data. Centered on ACLED, our pipeline transforms raw event records into a searchable knowledge graph and employs a Retrieval-Augmented Generation (RAG) system to feed relevant information into a Large Language Model (LLM) via tailored prompts. The prototype produces concise, context-aware summaries that follow a consistent structure and cite sources for traceability. To ensure factual reliability, we designed custom evaluation methods to detect hallucinations and measure consistency. The modular architecture is built to support future integration of unstructured data sources, laying the groundwork for a scalable early-warning system.

### Repository Structure
The repository is organized to support development, testing, and deployment of the tool. Below is the structure outlined in Section 6 of the report:

- `src/`: Contains the core Python scripts and modules.
  - `data_processing/`: Scripts for loading and processing ACLED data.
  - `visualization/`: Code for generating maps and charts (e.g., severity gradients).
  - `knowledge_graph/`: Neo4j integration for event and actor relationships.
  - `summary_generation/`: Logic for creating conflict briefs.
- `data/`: Raw and processed datasets (e.g., `acled_2024_multi.csv`, `regional_severity_2024.csv`).
- `docs/`: Documentation files, including this README and user guides.
- `tests/`: Unit tests for validating tool components.
- `requirements.txt`: Lists all dependencies (e.g., pandas, geopandas, matplotlib, neo4j).
- `setup.py`: Configuration for package installation.
- `README.md`: This file, providing an overview and setup instructions.

### How to Launch the App
1. **Clone the Repository**:
   - Run `git clone https://github.com/yourusername/conflict-monitoring-tool.git` to download the project.

2. **Set Up Environment**:
   - Ensure Docker and Docker Compose are installed (Docker 20.10.24+, Docker Compose 2.20.2+).
   - Create a virtual environment: `python -m venv venv`.
   - Activate and Install dependencies: `pip install -r requirements.txt`.

3. **Run with Docker Compose**:
- Navigate to the `docker/` directory.
- Run `docker-compose up --build` to start the application, MongoDB, and Neo4j containers.
- Access the Streamlit app at `http://localhost:8501`.
- The app will automatically process data and generate conflict briefs and visualizations.
