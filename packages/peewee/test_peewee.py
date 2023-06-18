from pytest_pyodide import run_in_pyodide


@run_in_pyodide(packages=["peewee"])
def test_peewee(selenium):
    import os

    from peewee import CharField, IntegerField, Model, SqliteDatabase

    db = SqliteDatabase(os.path.join("/tmp", "database.db"))
    # needs to be in '/tmp' for now, cf: https://github.com/jupyterlite/pyodide-kernel/issues/35

    # Define a model class
    class Person(Model):
        name = CharField()
        age = IntegerField()

        class Meta:
            database = db

    # Connect to the database, create tables, and bind the model
    with db:
        db.create_tables([Person])

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
