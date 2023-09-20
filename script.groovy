def buildImage() {
    echo "Starting application build"
    withCredentials([file(credentialsId: 'jenkins-gcr-account', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
        sh 'docker login -u _json_key -p "`cat ${GOOGLE_APPLICATION_CREDENTIALS}`" https://gcr.io'
        sh 'docker build -f Dockerfile . -t blackjack-backend-service'
        sh 'docker tag blackjack-backend-service gcr.io/mima-325516/blackjack/backend:dev'
    }
    echo "Image pushed to Google container registry"
}

def pushImage() {
    echo "Push Tested image to repo"
    withCredentials([file(credentialsId: 'jenkins-gcr-account', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
        sh 'docker login -u _json_key -p "`cat ${GOOGLE_APPLICATION_CREDENTIALS}`" https://gcr.io'
        sh 'docker push gcr.io/mima-325516/blackjack/backend:dev'
    }
    echo "Image  pushed to Google container registry"
}

def pushProdImage(){
    echo "Push Prod image to repo"
    withCredentials([file(credentialsId: 'jenkins-gcr-account', variable: 'GOOGLE_APPLICATION_CREDENTIALS')]) {
        sh 'docker login -u _json_key -p "`cat ${GOOGLE_APPLICATION_CREDENTIALS}`" https://gcr.io'
        sh 'docker pull gcr.io/mima-325516/blackjack/backend:dev'
        sh 'docker tag gcr.io/mima-325516/blackjack/backend:dev gcr.io/mima-325516/blackjack/backend:prod'
        sh 'docker push gcr.io/mima-325516/blackjack/backend:prod'
    }
    echo "Image pushed to Google container registry"
}

def TestApp() {
    echo "Starting unit test"
    sh 'docker network create mima_network && docker-compose -f docker-compose.test.yml up --build -d && docker-compose -f docker-compose.test.yml exec -T blackjack-backend-service pytest -s -vv && docker-compose -f docker-compose.test.yml down && docker network rm mima_network'
}

def deployToDev() {
    sh 'echo "starting deployment"'
    sh 'cd /var/lib/jenkins/workspace/configuration/ && /usr/local/bin/helm upgrade \
      --install  --wait --atomic blackjack-backend blackjack-backend   \
        --values /opt/configuration/dev/values-blackjack-backend.yaml  \
        --set image.releaseDate=VRSN`date +%Y%m%d-%H%M%S` --set image.tag=dev -n dev'
    echo "Core app deployed to dev"
}

def deployToProd() {
    sh 'echo "starting deployment"'
    sh 'cd /var/lib/jenkins/workspace/configuration/ && /usr/local/bin/helm upgrade \
      --install  --wait --atomic blackjack-backend blackjack-backend   \
        --values /opt/configuration/prod/values-blackjack-backend.yaml  \
        --set image.releaseDate=VRSN`date +%Y%m%d-%H%M%S` --set image.tag=dev -n prod'
    echo "Core app deployed to prod"
}

return this
