import json

with open("hermes_requests.json", "r") as data_file:
    data = json.load(data_file)

    for element in data["item"]:
        element["request"]["header"][0]["value"] = "Bearer "
        elem = element["request"]["body"]
        if "formdata" in elem:
            form = elem["formdata"]
            for elem in form:
                if elem["key"] == "youtube_access_token":
                    elem["value"] = ""

with open("hermes_requests.json", "w") as data_file:
    data = json.dump(data, data_file, indent = 4)
