from ui.app import create_gradio_app


def main() -> None:
    app = create_gradio_app()
    app.launch(inbrowser=True)


if __name__ == "__main__":
    main()
