import os
basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret'
    SSL_DISABLE = False

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True



class ProductionConfig(Config):
    DEBUG =  False


config = dict(
    development=DevelopmentConfig,
    production=ProductionConfig,
    default=DevelopmentConfig
)