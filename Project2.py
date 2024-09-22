#Guessing random number 
import random
endval=input("Enter the end of your desired range: ")
if endval.isdigit():
    endval=int(endval)

elif endval<=0 :

    print("Please enter a legitimate number next time")
else:
    print("please write a number next time")

randnum = random.randint(0,endval)
guess=0

while True:
    guess+=1
    userguess=input("Shoot out your Guess:")
    if userguess.isdigit():
        userguess=int(userguess)
    else:
        print("Please enter a number next time")
        continue
    if userguess==randnum:
        print("You got it right!")
        break
    elif userguess > randnum:
        print("Try lesser")
    else:
        print("Try Higher")

print("You guessed it in ",guess,"trials")


        

