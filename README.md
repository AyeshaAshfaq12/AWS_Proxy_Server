# FastAPI Reverse Proxy

This project is a lightweight, open-source reverse proxy built using FastAPI. It allows a single authenticated session with a third-party website to be shared securely across a maximum of 10 client devices. 

## Features

- **Single Authenticated Session**: Supports sharing of one authenticated session across multiple devices.
- **Secure Proxying**: Forwards requests to a target website while maintaining security and session integrity.
- **AWS Integration**: Utilizes AWS SSM for secure storage and retrieval of API keys and credentials.
- **Lightweight**: Built with FastAPI for high performance and low overhead.

## Project Structure

```
fastapi-reverse-proxy
├── src
│   ├── main.py          # Entry point of the FastAPI application
│   ├── api
│   │   └── proxy.py     # Core proxy logic
│   ├── auth
│   │   └── session.py   # Session authentication management
│   ├── aws
│   │   └── integration.py# AWS service interactions
│   └── utils
│       └── helpers.py   # Utility functions
├── requirements.txt      # Project dependencies
├── README.md             # Project documentation
├── manual_cookies.json             # cookies file
└── .env                  # Environment variables
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd fastapi-reverse-proxy
   ```

2. Create a virtual environment and activate it:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Configure your environment variables in the `.env` file.

5. Run the application:
   ```
   uvicorn src.main:app --reload
   ```

## Usage

- Send a POST request to `/proxy/{path}` to forward requests to the target website.
- Ensure that the API key is included in the headers for authentication.

## Architecture

The application is structured into several modules:

- **Main Module**: Initializes the FastAPI application and sets up the necessary routes and middleware.
- **API Module**: Contains the proxy logic that handles incoming requests and forwards them to the target website.
- **Auth Module**: Manages session authentication and ensures that the client is authenticated before forwarding requests.
- **AWS Module**: Interacts with AWS services to fetch necessary credentials securely.
- **Utils Module**: Provides helper functions for logging and error handling.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.

## License

This project is licensed under the MIT License. See the LICENSE file for more details.
