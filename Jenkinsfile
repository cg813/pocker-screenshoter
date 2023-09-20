def gv
pipeline{
    agent { label 'master' }
    environment {
        SERVER_CREDENTIALS = credentials('jenkins-gcr-account')
    }
    stages{
        stage("Load script") {
            steps {
                script {
                    gv = load "script.groovy"
                    env.GIT_COMMIT_MSG = sh (script: 'git log -1 --pretty=%B ${GIT_COMMIT} | head -n1', returnStdout: true).stripIndent().trim()
                    env.GIT_AUTHOR = sh (script: 'git log -1 --pretty=%ae ${GIT_COMMIT} | awk -F "@" \'{print $1}\' | grep -Po "[a-z]{1,}" | head -n1', returnStdout: true).trim()

                }
            }
        }
        stage("Build Image") {
            agent { label "builder" }
            steps {
              slackSend (color: '#00FF00', message: "Build - ${env.BUILD_NUMBER} ${env.JOB_NAME} Started ${env.BUILD_NUMBER}  by changes from ${env.GIT_AUTHOR} commit message ${env.GIT_COMMIT_MSG} (<${env.BUILD_URL}|Open>)")
                script {
                    gv.buildImage()
                }
            }
        }
        stage("Backend test") {
            agent { label "builder" }
            steps {
              slackSend (color: '#00FF00', message: "Backend unit test  - ${env.BUILD_NUMBER} ${env.JOB_NAME} Started  ${env.BUILD_NUMBER}  to check:  ${env.GIT_AUTHOR}'s commit message: ${env.GIT_COMMIT_MSG} (<${env.BUILD_URL}|Open>)")

                script {
                    gv.TestApp()
                }
              sh 'docker network prune  -f'
            }
        }
        stage("Push image to Repo") {
            when {
                branch 'master'
            }
            agent { label "builder" }
            steps {
              slackSend (color: '#00FF00', message: "Push tested ${env.BRANCH_NAME} image to repo No - ${env.BUILD_NUMBER} ${env.JOB_NAME} Started ${env.BUILD_NUMBER} (<${env.BUILD_URL}|Open>)")
                script {
                    gv.pushImage()
                }
            }
        }
        stage("Deploy to Development") {
            when {
                branch 'master'
            }
            steps {
              slackSend (color: '#00FF00', message: "Deployment of build#${env.BUILD_NUMBER} ${env.JOB_NAME} started for change form: ${env.GIT_AUTHOR} and commit message ${env.GIT_COMMIT_MSG} (<${env.BUILD_URL}|Open>)")
                script {
                    gv.deployToDev()
                }
            }
        }
        stage("Push image to Repo for production") {
            when {
                branch 'master'
            }
            agent { label "builder" }
            steps {
              slackSend (color: '#00FF00', message: "Pushing tested ${env.BRANCH_NAME} image to repo No - ${env.BUILD_NUMBER} ${env.JOB_NAME} Started ${env.BUILD_NUMBER} (<${env.BUILD_URL}|Open>)")
                script {
                    gv.pushProdImage()
                }
            }
        }
        stage("Deploy to Production") {
            when {
                branch 'master'
            }
            steps {
              slackSend (color: '#00FF00', message: "Deployment of build#${env.BUILD_NUMBER} ${env.JOB_NAME} started for change form: ${env.GIT_AUTHOR} and commit message ${env.GIT_COMMIT_MSG} (<${env.BUILD_URL}|Open>)")
                script {
                    gv.deployToProd()
                }
            }
        }
    }
    post {
        success {
            slackSend (color: '#00FF00', message: "Success  job '${env.JOB_NAME} [${env.BUILD_NUMBER}]' (<${env.BUILD_URL}|Open>)")
            }
        failure {
            slackSend (color: '#FF0000', message: "Failed: job '${env.JOB_NAME} [${env.BUILD_NUMBER}]' (<${env.BUILD_URL}|Open>)")
        }
        always {
            sh 'docker system prune -af --volumes'
            sh 'docker images prune -a'
            sh 'docker network prune  -f'
        }
    }
}



