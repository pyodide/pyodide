from pytest_pyodide import run_in_pyodide

import os
from peewee import SqliteDatabase, Model, CharField, IntegerField

@run_in_pyodide(packages=["peewee"])
def test_peewee(selenium):
    database = SqliteDatabase(os.path.join('/tmp', 'database.db'))

    # Define a model class
    class Person(Model):
        name = CharField()
        age = IntegerField()

        class Meta:
            database = database

    # Connect to the database, create tables, and bind the model
    with database:
        database.create_tables([Person])
        
        # Create a new person
        person = Person.create(name="John Doe", age=25)
        
        # Retrieve all people from the database
        people = Person.select()
        
        # Verify that the person was created and retrieved
        assert person in people
        
        # Update a person's age
        person.age = 30
        person.save()
        
        # Delete a person
        person.delete_instance()
        
        # Verify that the person was deleted
        assert person not in Person.select()