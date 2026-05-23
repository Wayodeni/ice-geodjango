#!/bin/bash

# TODO: Compilemessages from root of the project for all applications
LIGHT_GREEN='\033[1;32m'
NC='\033[0m' # No Color

color_print () {
  echo "${LIGHT_GREEN}===========================================${NC}"
  echo "${LIGHT_GREEN}$1${NC}"
  echo "${LIGHT_GREEN}===========================================${NC}"
}

color_print "Making migrations"
python3 manage.py makemigrations

color_print "Creating cache table"
python manage.py createcachetable

color_print "Applying migrations"
python3 manage.py migrate

# color_print "Compiling translation files"
# python3 manage.py compilemessages 

if [ "$ENVIRONMENT" = "DEV" ]; then

color_print "Creating superuser from compose ENV vars"
python3 manage.py createsuperuser --noinput

color_print "Starting development server"
python3 manage.py runserver 0.0.0.0:8000

elif [ "$ENVIRONMENT" = "PROD" ]; then

color_print "Collecting static files"
python3 manage.py collectstatic --noinput

color_print "Running gunicorn"
gunicorn --bind 0.0.0.0:8000 settings.wsgi:application --workers $(($(nproc) * 2 + 1)) --timeout 1600

fi

