


def create_notebook(timestamp):
    # Create new notebook structure
    notebook = {
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.12.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    # Add header cell for new notebook
    header_cell = {
        "cell_type": "markdown",
        "metadata": {},
        "source": [
            "# Azure RAG Query Log",
            "",
            "This notebook contains logged queries and responses from the Azure RAG Client.",
            f"**Created**: {timestamp}",
            "",
            "---"
        ]
    }

    return notebook



if __name__ =="__main__":
    pass