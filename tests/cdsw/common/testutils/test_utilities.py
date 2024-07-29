

class Object(object):
    def __contains__(self, key):
        return key in self.__dict__


