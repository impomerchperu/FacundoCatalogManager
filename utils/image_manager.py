import os
import shutil


class ImageManager:


    IMAGE_FOLDER = "resources/images"


    @staticmethod
    def save_image(source_path, product_code):

        if not source_path:
            return ""


        os.makedirs(
            ImageManager.IMAGE_FOLDER,
            exist_ok=True
        )


        extension = os.path.splitext(source_path)[1]


        filename = (
            product_code.upper()
            + extension.lower()
        )


        destination = os.path.join(
            ImageManager.IMAGE_FOLDER,
            filename
        )

        destination = destination.replace("\\", "/")


        shutil.copy(
            source_path,
            destination
        )


        return destination