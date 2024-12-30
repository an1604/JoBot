import json


class Post:
    def __init__(self, email, link, name, content):
        self._email = email
        self._link = link
        self._name = name
        self._content = content

    def __eq__(self, other):
        if isinstance(other, Post):
            return (self._link == other._link and
                    self._name == other._name)
        return False

    def __hash__(self):
        return hash((self._email, self._link, self._name))

    def to_dict(self):
        """
        Convert the Post instance to a dictionary.
        """
        return {
            "email": self._email,
            "link": self._link,
            "name": self._name,
            "content": self._content,
        }

    @classmethod
    def from_dict(cls, data):
        """
        Create a Post instance from a dictionary.
        """
        return cls(
            email=data.get("email"),
            link=data.get("link"),
            name=data.get("name"),
            content=data.get("content"),
        )

    def to_json(self):
        """
        Convert the Post instance to a JSON string.
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str):
        """
        Create a Post instance from a JSON string.
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
