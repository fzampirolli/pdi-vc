
import json

def convert_md_to_ipynb(md_file_path, ipynb_file_path):
    with open(md_file_path, 'r', encoding='utf-8') as f:
        md_content = f.read()

    cells = []
    # Split the markdown content by markdown headings to create separate cells
    # This is a simplified approach; a more robust parser would be needed for complex markdown
    sections = md_content.split('##')

    # The first section might be before the first '##', handle it as a markdown cell
    if sections[0].strip():
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [sections[0].strip()]
        })
    
    for section in sections[1:]:
        if not section.strip():
            continue
        
        # Assuming the first line after '##' is the heading for the cell
        # and the rest is markdown content
        lines = section.strip().split('\n')
        heading = '## ' + lines[0].strip()
        content = '\n'.join(lines[1:]).strip()

        # Add heading as a markdown cell
        cells.append({
            "cell_type": "markdown",
            "metadata": {},
            "source": [heading]
        })
        
        # Add content as another markdown cell if it exists
        if content:
            cells.append({
                "cell_type": "markdown",
                "metadata": {},
                "source": [content]
            })

    notebook_content = {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.11.0rc1"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    with open(ipynb_file_path, 'w', encoding='utf-8') as f:
        json.dump(notebook_content, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    md_file = "/home/ubuntu/vc_chapters_proposal.md"
    ipynb_file = "/home/ubuntu/vc_chapters_proposal.ipynb"
    convert_md_to_ipynb(md_file, ipynb_file)
