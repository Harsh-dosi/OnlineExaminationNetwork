pipeline {
 
    agent any
 
    stages {
        stage('Install Dependencies') {
            steps {
                bat 'python -m pip install -r requirements.txt'
            }
        }
        stage('Run Tests') {
            steps {
                bat 'python -m pytest -v'
            }
        }
        stage('Build Docker Image') {
            steps {
                bat 'docker build -t online-exam-network:1.0 .'
            }
        }
    }
}
