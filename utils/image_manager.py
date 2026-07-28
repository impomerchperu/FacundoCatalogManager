import os
import shutil


class ImageManager:
    @staticmethod
    def save_image(source_path, code):

        folder = "resources/images"

        os.makedirs(folder, exist_ok=True)

        extension = os.path.splitext(source_path)[1]

        filename = f"{code}{extension}"

        destination = os.path.join(folder, filename)

        # Evitar copiar el mismo archivo
        if os.path.abspath(source_path) != os.path.abspath(destination):
            shutil.copy(source_path, destination)

        return destination
