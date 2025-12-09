"""
Extract vocabulary from images and create an Anki-compatible import file.
Uses Azure Computer Vision OCR to extract text from textbook images.
"""
import os
import sys
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

# Azure Computer Vision configuration - load from environment variables
ENDPOINT = os.environ.get("AZURE_VISION_ENDPOINT")
KEY = os.environ.get("AZURE_VISION_KEY")

# Default folders - can be overridden via command line or environment
IMAGE_FOLDER = os.environ.get("IMAGE_FOLDER", "./images")
OUTPUT_FOLDER = os.environ.get("OUTPUT_FOLDER", "./output")

def extract_text_from_image(client, image_path):
    """Extract text from an image using Azure Computer Vision OCR."""
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
    
    result = client.analyze(
        image_data=image_data,
        visual_features=[VisualFeatures.READ]
    )
    
    extracted_text = []
    if result.read is not None:
        for block in result.read.blocks:
            for line in block.lines:
                extracted_text.append(line.text)
    
    return extracted_text

def main():
    # Validate environment variables
    if not ENDPOINT or not KEY:
        print("Error: Please set AZURE_VISION_ENDPOINT and AZURE_VISION_KEY environment variables.")
        print("See .env.example for details.")
        sys.exit(1)
    
    # Create output folder if it doesn't exist
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    
    # Create client
    client = ImageAnalysisClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(KEY)
    )
    
    # Get all images
    image_extensions = ('.jpg', '.jpeg', '.png', '.bmp', '.gif')
    images = [f for f in os.listdir(IMAGE_FOLDER) 
              if f.lower().endswith(image_extensions)]
    images.sort()
    
    print(f"Found {len(images)} images to process...")
    
    all_text = []
    for i, image_name in enumerate(images, 1):
        image_path = os.path.join(IMAGE_FOLDER, image_name)
        print(f"Processing {i}/{len(images)}: {image_name}")
        
        try:
            text_lines = extract_text_from_image(client, image_path)
            all_text.extend(text_lines)
            print(f"  Extracted {len(text_lines)} lines")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Print all extracted text
    print("\n" + "="*60)
    print("EXTRACTED TEXT FROM ALL IMAGES:")
    print("="*60)
    for line in all_text:
        print(line)
    
    # Save raw text to file for review
    raw_output = os.path.join(OUTPUT_FOLDER, "extracted_text_raw.txt")
    with open(raw_output, "w", encoding="utf-8") as f:
        f.write("\n".join(all_text))
    print(f"\nRaw text saved to: {raw_output}")

if __name__ == "__main__":
    main()
