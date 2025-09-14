from PIL import Image
import imagehash


def get_image_fingerprint(image_path_or_pil):
    '''
    Compute the perceptual has (phash) of an image to uniquely idenyify it.
    Accepts a file path or a PIL Image Object.
    '''
    
    if isinstance(image_path_or_pil, str):
        image = Image.open(image_path_or_pil)
    else:
        image = image_path_or_pil
    
    return str(imagehash.phash(image))