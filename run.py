from app import create_app

# Create the Flask app instance for gunicorn
app = create_app()

# For local development
def main() -> None:
    app.run(debug=True, host="127.0.0.1", port=5000)


if __name__ == "__main__":
    main()


# Production configuration for gunicorn
if __name__ != "__main__":
    # This runs when imported by gunicorn
    pass


