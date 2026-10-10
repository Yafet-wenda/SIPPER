"""Form bawaan Django yang dilengkapi atribut autocomplete.

Tanpa atribut ini manajer kata sandi tidak tahu kolom mana yang harus diisi,
sehingga pengguna harus mengetik ulang sandi secara manual dan Chrome
menandai formulirnya di konsol.
"""

from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm


class PasswordChangeFormDjango(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs['autocomplete'] = 'current-password'
        for nama in ('new_password1', 'new_password2'):
            self.fields[nama].widget.attrs['autocomplete'] = 'new-password'


class SetPasswordFormDjango(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nama in ('new_password1', 'new_password2'):
            self.fields[nama].widget.attrs['autocomplete'] = 'new-password'
