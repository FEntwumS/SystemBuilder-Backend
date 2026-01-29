# SystemBuilder-Backend
This contains the backend of the SystemBuilder, consisting of a Docker image containing LiteX and the interface script(s). Note that the dockerfile is configured to install LiteX automatically.

The SystemBuilder is based on LiteX, which can be found here: https://github.com/enjoy-digital/litex

## NOTICE:
This project is currently very much a work in progress, so some bugs and strange behaviours should be expected.
To use the SystemBuilder you need to build the Docker image.
One way to di this is to put the files from this repository into a directory, open the shell there and use 
```sh
$ docker build -t liteximg .
```
What matters is that the image has the name **liteximg**.
To use the image for the SystemBuilder, the docker engine must be running.
