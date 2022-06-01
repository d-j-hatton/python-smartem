===============================================================
Tools to trace cryoEM SPA processing results through EPU output
===============================================================


Installation
------------

An installation of `PostgreSQL <https://www.postgresql.org>`_ is required. The easiest way is to work 
in a ``conda`` environment and simply run ``conda install postgresql``.

After installation run 

.. code:: bash 

    smartem.init -d <path/to/where/data/will/go>

This will run basic database setup. Upon completion this should suggest running a command 
to set the environment variable ``SMARTEM_CREDENTIALS`` which will setup database access 
credentials for you. The database server is started with

.. code:: bash 

    smartem.start -d <path/to/where/data/will/go>

and once you no longer need the server it can be stopped with 

.. code:: bash 

    smartem.stop -d <path/to/where/data/will/go>

The ``smartem`` GUI can be launched (if there is a database server running) with 

.. code:: bash 

    smartem.launch
