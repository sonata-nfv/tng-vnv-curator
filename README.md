[![Build Status](http://jenkins.sonata-nfv.eu/buildStatus/icon?job=tng-vnv-curator/master)](https://jenkins.sonata-nfv.eu/job/tng-vnv-curator)


# Curator for 5GTANGO Verification and Validation
This is a [5GTANGO](http://www.5gtango.eu) component to coordinate the verification and validation activities of 5G Network Services.


<p align="center"><img src="https://github.com/sonata-nfv/tng-api-gtw/wiki/images/sonata-5gtango-logo-500px.png" /></p>

## What it is

The Curator acts as the intermediate module between the Planner and the Executor for all V&V tests activities. It is responsible for processing a Test Plan, preparing the SP environment for tests, triggering the execution and cleaning up the environment afterwards.



## Build from source code

```bash
```

## Run the docker image

```bash
docker pull registry.sonata-nfv.eu:5000/tng-vnv-curator
docker run -d --name tng-vnv-curator -p 6200:6200 registry.sonata-nfv.eu:5000/tng-vnv-curator
```

### Health checking

### Swagger UI

## Dependencies

- `docker (18.x)`

## Contributing
Contributing to the Curator is really easy. You must:

1. Clone [this repository](http://github.com/sonata-nfv/tng-vnv-curator);
1. Work on your proposed changes, preferably through submiting [issues](https://github.com/sonata-nfv/tng-vnv-curator/issues);
1. Submit a Pull Request;
1. Follow/answer related [issues](https://github.com/sonata-nfv/tng-vnv-curator/issues) (see Feedback, below).


## License

This 5GTANGO component is published under Apache 2.0 license. Please see the [LICENSE](LICENSE) file for more details.

## Lead Developers

The following lead developers are responsible for this repository and have admin rights. They can, for example, merge pull requests.

* Juan Luis de la Cruz ([juanlucruz](https://github.com/juanlucruz))
* Felipe Vicens ([felipevicens](https://github.com/felipevicens))
* José Bonnet ([jbonnet](https://github.com/jbonnet))

## Feedback

Please use the [GitHub issues](https://github.com/sonata-nfv/tng-vnv-curator/issues) and the 5GTANGO Verification and Validation group mailing list `5gtango-dev@list.atosresearch.eu` for feedback.
