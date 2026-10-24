pipeline {
 
    agent any
 
    stages {
        stage('Install Dependencies') {
            steps {
                bat '"C:\\Users\\Harsh\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" -m pip install -r requirements.txt'
            }
        }
        stage('Run Tests') {
            steps {
                bat '"C:\\Users\\Harsh\\AppData\\Local\\Programs\\Python\\Python313\\python.exe" -m pytest -v'
            }
        }
       stage('Build Docker Image') {
    steps {
        bat '"C:\\Users\\Harsh\\AppData\\Local\\Programs\\DockerDesktop\\resources\\bin\\docker.exe" build -t online-exam-network:1.0 .'
    }
}
    }
}
