if __name__ == '__main__':
    from ios_ci.celery import app

    app.start(["", "worker", "-l", "info"])
