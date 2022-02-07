import abstract_api
from config import HOST


class LocalizeRequest(abstract_api.BaseRequest):
    """
    Localize uploaded image. Return camera pose and optional objects info and scene.
    Objects info and scene are sent on coordinate system change.
    """

    def __init__(self, method, url=None, params=None, data=None, headers=None, files=None, cookies=None):
        self.method = method
        self.params = params
        self.headers = headers
        self.data = data
        self.files = files
        self.cookies = cookies

        if url is None:
            self.url = f"{HOST}/api/localizer/localize"
        else:
            self.url = url

    def execute(self):
        return self._execute_localize()


class GetReconstructionsJsonRequest(abstract_api.BaseRequest):
    """
    Get scale
    """

    def __init__(self, method, url=None, params=None, data=None, headers=None, files=None, cookies=None):
        self.method = method
        self.params = params
        self.headers = headers
        self.data = data
        self.files = files
        self.cookies = cookies

        if url is None:
            self.url = f"{HOST}/rpc/get_reconstructions_json"
        else:
            self.url = url

    def execute(self):
        return self._execute()


class GetReconstructionPly(abstract_api.BaseRequest):
    """
    Get ply
    """

    def __init__(self, method, url=None, params=None, data=None, headers=None, files=None, cookies=None):
        self.method = method
        self.params = params
        self.headers = headers
        self.data = data
        self.files = files
        self.cookies = cookies

        if url is None:
            self.url = f"{HOST}/rpc/get_reconstruction_ply"
        else:
            self.url = url

    def execute(self):
        return self._execute_binary()


class LocalizeByGeopose(abstract_api.BaseRequest):
    """
    """
    def __init__(self, method, url=None, params=None, data=None, headers=None, files=None, cookies=None):
        self.method = method
        self.params = params
        self.headers = headers
        self.data = data
        self.files = files
        self.cookies = cookies

        if url is None:
            self.url = f"{HOST}/scrs/geopose_objs_local"
        else:
            self.url = url

    def execute(self):
        return self._execute()
