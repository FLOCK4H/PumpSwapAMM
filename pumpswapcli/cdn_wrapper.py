import os
import json
import requests
import uuid
try: from colors import *;
except: from .colors import *;

class BunnyCDNUploader:
    """
    A class to handle uploading files to Bunny.net Storage Zone
    and creating JSON metadata for image files.
    """

    def __init__(self,
                 region: str,
                 storage_zone_name: str,
                 access_key: str,
                 pull_zone_name: str):
        """
        :param region: Short region code per Bunny docs (e.g. 'uk', 'ny', '').
        :param storage_zone_name: Name of your Bunny Storage Zone.
        :param access_key: The Storage Zone API key.
        """
        self.create_folder("tmp")
        self.region = region
        self.storage_zone_name = storage_zone_name
        self.access_key = access_key

        base_url = "storage.bunnycdn.com"
        if self.region:
            base_url = f"{self.region}.{base_url}"
        self.upload_base_url = base_url
        self.download_base_url = f"{pull_zone_name}.b-cdn.net"

    def create_folder(self, folder_name: str):
        if not os.path.exists(folder_name):
            os.makedirs(folder_name, exist_ok=True)

    def upload_file(self, file_path: str, remote_filename: str) -> str:
        """
        Uploads a single file to Bunny CDN Storage and returns the public URL.

        :param file_path: Local path to the file.
        :param remote_filename: Filename (including directories) in Bunny Storage.
        :return: The final file URL on Bunny Storage.
        :raises Exception: If response from Bunny is not 201.
        """
        upload_url = f"https://{self.upload_base_url}/{self.storage_zone_name}/{remote_filename}"
        headers = {
            "AccessKey": self.access_key,
            "Content-Type": "application/octet-stream",
            "accept": "application/json"
        }

        with open(file_path, "rb") as file_data:
            response = requests.put(upload_url, data=file_data, headers=headers)

        if response.status_code != 201:
            raise Exception(
                f"Upload failed: {response.status_code} {response.text}"
            )
        
        download_url = f"https://{self.download_base_url}/{remote_filename}"
        return download_url

    def upload_image_and_metadata(self,
                                  image_path: str,
                                  name: str,
                                  symbol: str,
                                  description: str) -> str:
        """
        Uploads an image and corresponding JSON metadata to Bunny CDN.

        :param image_path: Local path to the image file.
        :param name: Name field for JSON metadata.
        :param symbol: Symbol field for JSON metadata.
        :param description: Description field for JSON metadata.
        :return: The URL of the uploaded metadata JSON on Bunny Storage.
        """
        cprint("Uploading image...")
        image_filename = os.path.basename(image_path)
        try:
            image_url = self.upload_file(image_path, f"assets/{image_filename}")
        except Exception as e:
            print(f"Error uploading image: {e}")
            return None
        
        cprint("Creating metadata JSON...")
        metadata = {
            "name": name,
            "symbol": symbol,
            "description": description,
            "image": image_url
        }
        unique_id = str(uuid.uuid4())
        metadata_filename = f"{unique_id}.json"
        metadata_path = os.path.join("tmp", metadata_filename)
        with open(metadata_path, "w", encoding="utf-8") as file_out:
            json.dump(metadata, file_out)

        cprint("Uploading metadata...")
        try:
            metadata_url = self.upload_file(metadata_path, f"metadata/{metadata_filename}")
        except Exception as e:
            print(f"Error uploading metadata: {e}")
            return None
        
        with open(metadata_path, "w", encoding="utf-8") as file_out:
            metadata["url"] = metadata_url
            json.dump(metadata, file_out)

        cprint(f"[Upload] image => {image_url}")
        cprint(f"[Upload] metadata => {metadata_url}")
        return metadata_url
