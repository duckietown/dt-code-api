from flask import Flask
from flask_cors import CORS

from .actions.status import status


class CodeAPI(Flask):

    def __init__(self):
        super(CodeAPI, self).__init__(__name__)
        # register blueprints
        self.register_blueprint(status)
        # apply CORS settings
        CORS(self)
