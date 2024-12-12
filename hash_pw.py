import getpass

import model


pw = getpass.getpass()
print(model.hash_password(model.SALT, pw))