import json
import logging
from json import JSONDecodeError
from pathlib import Path

import requests


class BaseRequest:
    def _execute_localize(self):
        response = getattr(requests, self.method)(self.url, params=self.params, data=self.data,
                                                  headers=self.headers, files=self.files, cookies=self.cookies)
        self._simple_report(response)
        return response

    def _execute(self):
        response = getattr(requests, self.method)(self.url, params=self.params, data=self.data,
                                                  headers=self.headers, files=self.files, cookies=self.cookies)
        self._simple_report(response)
        return response

    def _execute_binary(self):
        response = getattr(requests, self.method)(self.url, params=self.params, data=self.data,
                                                  headers=self.headers, files=self.files, cookies=self.cookies)
        self._with_binary_report(response)
        return response

    def _with_image_name_report(self, response, filename):
        try:
            logging.getLogger().info(f"URL: {response.request.url}\n"
                                     f"Method: {self.method}\n"
                                     f"Status code: {response.status_code}\n"
                                     f"{json.dumps(json.loads(response.text), indent=2)}\n"
                                     f"Image: {filename}")
        except JSONDecodeError:
            logging.getLogger().info(f"URL: {response.request.url}\n"
                                     f"Method: {self.method}\n"
                                     f"Status code: {response.status_code}\n"
                                     f"{response.text}")

    def _with_binary_report(self, response):
        logging.getLogger().info(f"URL: {response.request.url}\n"
                                 f"Method: {self.method}\n"
                                 f"Status code: {response.status_code}\n"
                                 f"BINARY FILE")

    def _simple_report(self, response):
        try:
            logging.getLogger().info(f"URL: {response.request.url}\n"
                                     f"Method: {self.method}\n"
                                     f"Status code: {response.status_code}\n"
                                     f"{json.dumps(json.loads(response.text), indent=2)}\n")
        except JSONDecodeError:
            logging.getLogger().info(f"URL: {response.request.url}\n"
                                     f"Method: {self.method}\n"
                                     f"Status code: {response.status_code}\n"
                                     f"{response.text}")
