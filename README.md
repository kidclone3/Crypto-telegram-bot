# Telegram Bot

This is an asynchronous Telegram bot built using Python.

## Prerequisites

- Python 3.11 or higher
- A Telegram bot token (you can get one from [BotFather](https://core.telegram.org/bots#botfather))

## Setup

1. Clone the repository:

    ```sh
    git clone <repository-url>
    cd <repository-directory>
    ```

2. Create a virtual environment:

    ```sh
    python3 -m venv venv
    ```

3. Activate the virtual environment:

    - On Windows:

        ```sh
        .\venv\Scripts\activate
        ```

    - On macOS/Linux:

        ```sh
        source venv/bin/activate
        ```

4. Install the required dependencies:

    ```sh
    pip install -r requirements.txt
    ```

5. Create a [.env](http://_vscodecontentref_/0) file in the root directory and add your Telegram bot token:

    ```env
    TELEGRAM_BOT_TOKEN=your-telegram-bot-token
    ```

## Running the Bot

1. Ensure your virtual environment is activated.

2. Run the bot:

    ```sh
    python src/main.py
    ```

Or if you have tmux installed, you can run the bot in a tmux session:

```sh
bash check_tmuxp.sh
```

## Additional Information

- The bot's functionality can be extended by modifying the [bot-telegram-async.py](http://_vscodecontentref_/1) file.
- Utility functions are available in the [utils.py](http://_vscodecontentref_/2) file.

## License

This project is licensed under the MIT License.