find all -path '*/cap*/*.ipynb' -print0 | xargs -0 grep -nB8 'from IPython.display import HTML'
