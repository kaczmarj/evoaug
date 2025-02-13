from setuptools import setup, find_packages


setup(
    name="evoaug",
    version="0.1.1",
    packages=find_packages(),
    description = "A Python package that trains models with evolution-inspired data augmentations. ",
    python_requires=">=3.6",
    install_requires=[
        'pytorch', 
        'pytorch_lightning', 
        'numpy'],
)
