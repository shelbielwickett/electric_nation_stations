import base64

with open("images/Electric-Nation.png", "rb") as image_file:
    encoded = base64.b64encode(image_file.read()).decode()

with open("images/logo_base64.txt", "w") as output:
    output.write(encoded)