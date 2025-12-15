# Free AI Hospital for 8 Billion People

## Mission
Our goal is to provide free, accessible, and high-quality AI-driven healthcare consultations to every person on Earth, regardless of their location or ability to pay.

## Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-repo/hai.git
    cd hai
    ```

2.  **Install dependencies:**
    ```bash
    make install
    ```

3.  **Run the application:**
    ```bash
    make run
    ```

## Architecture

```
                               +-----------------+
                               |                 |
      +----------------------> |   SIP Server    +---------------------->+
      |                        | (e.g., Asterisk)|                       |
      |                        +-----------------+                       |
      |                                ^                               |
      |                                |                               |
+-----+-----+                          | SIP/RTP                       |
|           |                          v                               |
|   User    |      +-------------------+-------------------+           |
| (Patient) |      |                                       |           v
+-----+-----+      |      Free AI Hospital Core System     |     +-----------+
      |            |                                       |     |           |
      |            |  +---------+      +-------+       +---+   |  Database   |
      +--------------> |   STT   | ---> |  AI   | ----> | TTS |   |           |
        Audio In     | (Speech- |      | (LLM) |       +---+   | (Postgres)  |
                     | to-Text)  |      +-------+         |     +-----------+
                     +---------+          ^             |           ^
                                          |             |           |
                                          |             v           |
                               +----------v-----------+ |           |
                               |  Vector Store & PII | |           |
                               | (ChromaDB, Presidio)| |           |
                               +---------------------+ v           |
                                           |           |           |
                                           +-----------+-----------+
                                             (Data Access Layer)

```

## Badges
[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/your-repo/hai)
[![Python Version](https://img.shields.io/badge/python-3.11-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## Documentation
[Link to full documentation (Coming Soon)]()

## Contributors
We welcome contributions from everyone. See [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

## Disclaimer
This project is for research and informational purposes only. It is **not a replacement for a real doctor** or professional medical advice. In a medical emergency, call your local emergency services immediately.
