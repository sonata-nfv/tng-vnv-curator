pipeline {
  agent any
  stages {
    stage('Container Build') {
      parallel {
        stage('Container Build') {
          steps {
            echo 'Building...'
          }
        }
        stage('Building tng-vnv-curator') {
          steps {
            sh 'docker build -t registry.sonata-nfv.eu:5000/tng-vnv-curator .'
          }
        }
      }
    }
    stage('Unit Test') {
      parallel {
        stage('Unit Tests') {
          steps {
            echo 'Performing Unit Tests'
          }
        }
        stage('Running Unit Tests') {
          steps {
            echo 'TODO'
          }
        }
      }
    }
    stage('Containers Publication') {
      parallel {
        stage('Containers Publication') {
          steps {
            echo 'Publication of containers in local registry....'
          }
        }
        stage('Publishing tng-vnv-curator') {
          steps {
            sh 'docker push registry.sonata-nfv.eu:5000/tng-vnv-curator'
          }
        }
      }
    }
    stage('Deployment in Integration') {
      parallel {
        stage('Deployment in Integration') {
          steps {
            echo 'Deploying in integration...'
          }
        }
        stage('Deploying') {
          steps {
            sh 'rm -rf tng-devops || true'
            sh 'git clone https://github.com/sonata-nfv/tng-devops.git'
            dir(path: 'tng-devops') {
              sh 'ansible-playbook roles/vnv.yml -i environments -e "target=pre-int-vnv component=tng-vnv-curator"'
            }
          }
        }
      }
    }
    stage('Promoting containers to integration env') {
      when {
         branch 'master'
      }
      parallel {
        stage('Publishing containers to int') {
          steps {
            echo 'Promoting containers to integration'
          }
        }
        stage('tng-vnv-curator') {
          steps {
            sh 'docker tag registry.sonata-nfv.eu:5000/tng-vnv-curator:latest registry.sonata-nfv.eu:5000/tng-vnv-curator:int'
            sh 'docker push registry.sonata-nfv.eu:5000/tng-vnv-curator:int'
          }
        }
        stage('Promoting to integration') {
          when{
            branch 'master'
          }
          steps {
            sh 'docker tag registry.sonata-nfv.eu:5000/tng-vnv-curator:latest registry.sonata-nfv.eu:5000/tng-vnv-curator:int'
            sh 'docker push registry.sonata-nfv.eu:5000/tng-vnv-curator:int'
            sh 'rm -rf tng-devops || true'
            sh 'git clone https://github.com/sonata-nfv/tng-devops.git'
            dir(path: 'tng-devops') {
              sh 'ansible-playbook roles/vnv.yml -i environments -e "target=int-vnv component=tng-vnv-curator"'
            }
          }
        }
      }
    }
    stage('Promoting release v5.1') {
      when {
        branch 'v5.1'
      }
      stages {
        stage('Generating release') {
          steps {
            sh 'docker tag registry.sonata-nfv.eu:5000/tng-vnv-curator:latest registry.sonata-nfv.eu:5000/tng-vnv-curator:v5.1'
            sh 'docker tag registry.sonata-nfv.eu:5000/tng-vnv-curator:latest sonatanfv/tng-vnv-curator:v5.1'
            sh 'docker push registry.sonata-nfv.eu:5000/tng-vnv-curator:v5.1'
            sh 'docker push sonatanfv/tng-vnv-curator:v5.1'
          }
        }
      }
    }
  }
  post {
    always {
      echo 'TODO'
    }
  }
}
